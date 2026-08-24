"""
All the "AI" logic in one place: skill taxonomy, the three-tier skill match
cascade, BGE-M3 semantic similarity, and the hybrid S1 formula.
"""

import csv
import re
from pathlib import Path
from functools import lru_cache
from collections import defaultdict

from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
import numpy as np

DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# 1. Skill taxonomy -- loaded from data/01_skill_taxonomy.csv
#    columns: category, canonical_skill, fuzzy_variants (";"-separated), contextual_paraphrase
# ---------------------------------------------------------------------------


def _load_taxonomy():
    skills = defaultdict(list)
    fuzzy_variants = {}
    contextual_phrases = {}

    with open(DATA_DIR / "01_skill_taxonomy.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            category = row["category"].strip()
            skill = row["canonical_skill"].strip()
            skills[category].append(skill)

            variants = [v.strip() for v in row.get("fuzzy_variants", "").split(";") if v.strip()]
            if variants:
                fuzzy_variants[skill] = variants

            paraphrase = row.get("contextual_paraphrase", "").strip()
            if paraphrase:
                contextual_phrases[skill] = paraphrase

    return dict(skills), fuzzy_variants, contextual_phrases


SKILLS, FUZZY_VARIANTS, CONTEXTUAL_PHRASES = _load_taxonomy()
ALL_SKILLS = sorted({s for skills in SKILLS.values() for s in skills})

# ---------------------------------------------------------------------------
# Tunable constants -- values below are the winners of the grid search over
# the 250 gold pairs in the eval dataset (see evaluate_dataset.py / the
# Sweep A + Sweep B notebook cells), not hand-picked defaults:
#
#   Sweep A (semantic_weight x contextual_threshold, cutoffs held at 70/40):
#       best -> semantic_weight=0.30, contextual_threshold=0.65
#       (tier_accuracy=0.928, overall_mcc=0.8937 at that point)
#   Sweep B (best_cut x avg_cut, semantic_weight/threshold held at the
#            Sweep A winner):
#       best -> best_cut=65, avg_cut=40
#       (tier_accuracy=0.936, overall_mcc=0.8996 -- the final config)
#
# Re-run the sweep (with a larger/updated gold set) and update these five
# numbers if the taxonomy or dataset changes meaningfully.
# ---------------------------------------------------------------------------

CONTEXTUAL_THRESHOLD = 0.65
TIER_WEIGHTS = {"exact": 1.0, "fuzzy": 0.85, "contextual": 0.70, "none": 0.0}

SEMANTIC_WEIGHT = 0.30
SKILL_WEIGHT = 0.70

BEST_CUT = 65
AVERAGE_CUT = 40

# ---------------------------------------------------------------------------
# 2. Embedder (loaded once per process)
#
# Swapped from all-MiniLM-L6-v2 to BAAI/bge-m3. BGE-M3 is exposed through
# the sentence-transformers library the same way MiniLM was, so encode()
# with normalize_embeddings=True works identically -- no other code in this
# file needs to change. The reason for the swap: MiniLM silently truncates
# any input past 256 tokens, so a long resume's later sections (often where
# the most relevant experience sits) were never actually seen by the
# embedder. BGE-M3 supports inputs up to 8192 tokens, so this stage now
# reads the whole resume instead of a ~200-word prefix of it. The tradeoff
# is that BGE-M3 (~569M params) is much heavier than MiniLM (~22M params),
# so embedding calls are slower -- acceptable here since, per Section V of
# the paper, the encoder loads once at process start and JD embeddings are
# reused across the whole applicant pool for a posting, not recomputed
# per-request.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_embedder():
    return SentenceTransformer("BAAI/bge-m3")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


# ---------------------------------------------------------------------------
# 2b. Noise-stripping for the SEMANTIC path only.
#
# IMPORTANT: this is intentionally NOT applied before the skill-cascade
# matching functions (_exact_match / _fuzzy_match / _contextual_match) --
# those need the raw resume text as-is so skills are still found wherever
# they appear. It is only applied to the text handed to the embedder for
# the document-level Phi_sem similarity score, since contact details,
# links, and boilerplate contribute nothing to "does this resume's meaning
# match this job description's meaning" and only dilute that embedding.
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+|linkedin\.com/\S+|github\.com/\S+)", re.IGNORECASE)
# Candidate phone-like runs: digit optionally grouped with spaces, dashes,
# dots, or parentheses. This alone would also match short things like a
# "2019-2023" date range, so it's filtered below by actual digit count --
# a real phone number has 9+ digits; a date range like "2019-2023" only has 8.
_PHONE_CANDIDATE_RE = re.compile(r"(\+?\d[\d\-\.\s\(\)]{5,}\d)")
_MULTI_WS_RE = re.compile(r"\s+")


def _strip_phone_numbers(text: str) -> str:
    def _replace_if_phone(match: re.Match) -> str:
        digit_count = sum(1 for ch in match.group(0) if ch.isdigit())
        return " " if digit_count >= 9 else match.group(0)

    return _PHONE_CANDIDATE_RE.sub(_replace_if_phone, text)


def clean_for_semantic(text: str) -> str:
    """
    Strips emails, URLs, and phone numbers before the text is embedded for
    Phi_sem (document-level semantic similarity). Does NOT touch skill
    tokens, dates (e.g. "2019-2023"), or section headers -- those still
    carry meaning that matters for matching. Safe no-op on text that has
    none of this noise.
    """
    if not text:
        return text

    cleaned = _EMAIL_RE.sub(" ", text)
    cleaned = _URL_RE.sub(" ", cleaned)
    cleaned = _strip_phone_numbers(cleaned)
    cleaned = _MULTI_WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[\n\r]+|(?<=[.;])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


# ---------------------------------------------------------------------------
# 3. Three-tier skill match: Theta_skill = (1/|K_jd|) * sum Psi(k_i, L_res)
# ---------------------------------------------------------------------------


def _exact_match(skill: str, resume_norm: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, resume_norm) is not None


def _fuzzy_threshold_for(skill: str) -> float:
    """
    Shorter skills (e.g. 'R', 'Go', 'C++') need a tight threshold -- a single
    edit is a huge fraction of the string, and loosening it globally causes
    false positives on unrelated short tokens. Longer multi-word skills can
    tolerate more relative edit distance since one typo moves the ratio less.
    """
    length = len(skill)
    if length <= 4:
        return 92.0
    elif length <= 8:
        return 85.0
    else:
        return 78.0


def _fuzzy_match(skill: str, resume_norm: str) -> bool:
    """
    RapidFuzz-based fuzzy matching. Checks multiple window sizes around the
    skill's word count (not just an exact match) so typos that merge or
    split words ("MachineLearning", "Machine Learining") are still caught.

    NOTE: intentionally uses only ratio + token_sort_ratio, NOT
    partial_ratio. partial_ratio matches a short string against any
    substring of a longer one, which makes it too lenient here -- it was
    catching windows that only partially overlapped the skill (e.g. picking
    up unrelated neighboring words), stealing cases that should have fallen
    through to the contextual tier and tanking contextual recall. ratio +
    token_sort_ratio catch real typos/reordering without that side effect.
    """
    candidates = [skill] + FUZZY_VARIANTS.get(skill, [])
    words = resume_norm.split()
    threshold = _fuzzy_threshold_for(skill)

    for cand in candidates:
        cand_norm = _normalize(cand)
        cand_word_count = max(1, len(cand_norm.split()))

        # Check windows one word shorter/longer than expected, to catch
        # typos that merge two words into one or split one into two.
        spans = {s for s in (cand_word_count - 1, cand_word_count, cand_word_count + 1) if s > 0}

        for span in spans:
            windows = [" ".join(words[i:i + span]) for i in range(max(0, len(words) - span + 1))]
            for w in windows:
                if not w:
                    continue
                score = max(fuzz.ratio(cand_norm, w), fuzz.token_sort_ratio(cand_norm, w))
                if score >= threshold:
                    return True
    return False


# ---------------------------------------------------------------------------
# 3b. Contextual-tier caching.
#
# Previously, _contextual_match() re-split and re-embedded the resume's
# sentences from scratch on every call -- and match_skill() is called once
# per required skill for the same resume (skill_match_ratio loops over
# required_skills; evaluate_dataset.py's skill-cascade eval loops over every
# labeled skill for every resume). For a JD with 10 required skills that
# meant re-encoding the same resume text up to 10 times.
#
# Fixed by splitting + embedding each resume's sentences exactly once
# (cached on the raw resume_text) and reusing that per-resume embedding
# matrix across every skill check against that resume. The per-skill
# contextual phrase embedding is cached the same way, since a skill's
# CONTEXTUAL_PHRASES entry doesn't change between resumes.
#
# Cache sizes are generous but bounded (not lru_cache(maxsize=None)) so a
# very long eval run doesn't grow memory unboundedly; ALL_SKILLS is a fixed,
# small taxonomy so its cache never needs eviction, while resumes can number
# in the thousands across a run.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _cached_resume_sentences_and_embeddings(resume_text: str):
    """
    Splits a resume into sentences and embeds all of them in a single
    batched encode() call. Cached per resume_text so repeated contextual
    checks against the same resume (one per required/labeled skill) reuse
    this instead of re-splitting and re-encoding every time.
    """
    sentences = _split_sentences(resume_text)
    if not sentences:
        return tuple(), None

    embedder = get_embedder()
    vecs = embedder.encode(sentences, batch_size=32, normalize_embeddings=True)
    return tuple(sentences), vecs


@lru_cache(maxsize=None)
def _cached_phrase_embedding(phrase: str):
    embedder = get_embedder()
    return embedder.encode([phrase], normalize_embeddings=True)[0]


def _contextual_match(skill: str, resume_text: str) -> bool:
    phrase = CONTEXTUAL_PHRASES.get(skill)
    if not phrase:
        return False

    sentences, sent_vecs = _cached_resume_sentences_and_embeddings(resume_text)
    if not sentences:
        return False

    phrase_vec = _cached_phrase_embedding(phrase)

    skill_lower = skill.lower()
    candidate_indices = [i for i, s in enumerate(sentences) if skill_lower not in s.lower()]
    if not candidate_indices:
        return False

    best = max(float(sent_vecs[i] @ phrase_vec) for i in candidate_indices)
    return best >= CONTEXTUAL_THRESHOLD


def match_skill(skill: str, resume_text: str) -> dict:
    resume_norm = _normalize(resume_text)

    if _exact_match(skill, resume_norm):
        tier = "exact"
    elif _fuzzy_match(skill, resume_norm):
        tier = "fuzzy"
    elif _contextual_match(skill, resume_text):
        tier = "contextual"
    else:
        tier = "none"

    return {"skill": skill, "tier": tier, "weight": TIER_WEIGHTS[tier]}


def skill_match_ratio(required_skills: list[str], resume_text: str) -> tuple[float, list[dict]]:
    if not required_skills:
        return 0.0, []
    matches = [match_skill(s, resume_text) for s in required_skills]
    theta = sum(m["weight"] for m in matches) / len(required_skills)
    return round(theta, 4), matches


# ---------------------------------------------------------------------------
# 4. Semantic similarity + hybrid S1 score
#    Phi_sem = max(0, min(1, cosine(E(resume), E(jd))))
#    S1 = (SEMANTIC_WEIGHT * Phi_sem + SKILL_WEIGHT * Theta_skill) * 100
# ---------------------------------------------------------------------------


def embed_resume(resume_text: str) -> np.ndarray | None:
    """
    Embeds a resume the same way semantic_similarity() does internally
    (noise-stripped via clean_for_semantic). Exposed as its own function so
    callers can compute the embedding once and pass it into
    score_application() via resume_vec, instead of letting
    semantic_similarity() re-embed the resume on every call.

    Returns None if the resume is empty/unparseable after noise-stripping
    (e.g. a resume that is nothing but an email address and a phone number)
    rather than encoding an empty string, which some sentence-transformers
    backends handle inconsistently.
    """
    resume_clean = clean_for_semantic(resume_text)
    if not resume_clean:
        return None
    embedder = get_embedder()
    return embedder.encode([resume_clean], normalize_embeddings=True)[0]


def semantic_similarity(resume_text: str, jd_text: str, resume_vec: np.ndarray = None) -> float:
    # Noise-stripped only for the embedding step -- the raw resume_text
    # passed into score_application() below is untouched, so skill_match_ratio()
    # still sees the full original text.
    jd_clean = clean_for_semantic(jd_text)
    if not jd_clean:
        # No usable JD text to compare against -- fall back to 0.0 instead
        # of encoding an empty string and letting a degenerate embedding
        # flow into the cosine calculation below.
        return 0.0

    if resume_vec is None:
        resume_vec = embed_resume(resume_text)
    if resume_vec is None:
        # Resume was empty/unparseable after noise-stripping -- no basis
        # for a semantic comparison, so score it as no match rather than
        # crashing on an empty embedding.
        return 0.0

    embedder = get_embedder()
    jd_vec = embedder.encode([jd_clean], normalize_embeddings=True)[0]
    cosine = float(np.dot(resume_vec, jd_vec))
    return round(max(0.0, min(1.0, cosine)), 4)


def score_application(
    resume_text: str,
    jd_text: str,
    required_skills: list[str],
    resume_vec: np.ndarray = None,
) -> dict:
    phi_sem = semantic_similarity(resume_text, jd_text, resume_vec=resume_vec)
    theta_skill, matches = skill_match_ratio(required_skills, resume_text)
    s1 = round((SEMANTIC_WEIGHT * phi_sem + SKILL_WEIGHT * theta_skill) * 100, 2)

    tier = "Low"
    if s1 >= BEST_CUT:
        tier = "Best"
    elif s1 >= AVERAGE_CUT:
        tier = "Average"

    return {
        "phi_sem": phi_sem,
        "theta_skill": theta_skill,
        "screening_score": s1,
        "tier": tier,
        "skill_matches": matches,
    }