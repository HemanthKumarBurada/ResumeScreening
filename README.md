# ATS — Simplified (Python backend + Next.js frontend + PostgreSQL)

Two folders only, as requested: `backend/` (FastAPI, talks to Postgres
directly with SQLAlchemy) and `frontend/` (Next.js). No Node backend, no
separate ML microservice — the SBERT/skill-matching logic lives in
`backend/matcher.py` and is called in-process by `backend/main.py`.

## Formulas, and where they live

- `Φ_sem` (semantic similarity) and `S1` (hybrid score) → `matcher.py::semantic_similarity`, `matcher.py::score_application`
- `Θ_skill` (3-tier skill cascade: exact → fuzzy → contextual) → `matcher.py::skill_match_ratio`
- `S1 = (0.70·Φ_sem + 0.30·Θ_skill) × 100`

## 1. Install PostgreSQL (Windows)

Download from postgresql.org and install (default port 5432). Then, using
pgAdmin or `psql`:

```sql
CREATE USER ats_user WITH PASSWORD 'ats_password';
CREATE DATABASE ats_db OWNER ats_user;
```

Tables are created automatically the first time you run the backend
(`Base.metadata.create_all` in `main.py`) — no separate schema file to run.

## 2. Run the backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` (copy `.env.example`) with your DB
credentials, then:

```powershell
uvicorn main:app --reload --port 8000
```

Check http://localhost:8000/docs — first request will download the SBERT
model (~90MB), one-time only.

## 3. Run the frontend

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```powershell
npm run dev
```

Open http://localhost:3000.

## 4. Connect VS Code to Postgres

Install a Postgres extension (e.g. `cweijan.vscode-postgresql-client2`), add
a connection:
```
Host: localhost
Port: 5432
User: ats_user
Password: ats_password
Database: ats_db
```
SSL: disable. Connect, and you'll see `job_postings`, `candidates`,
`applications` once the backend has run at least once.

## 5. Walkthrough

1. http://localhost:3000/post-job — post a job. Use skill names from
   `matcher.py`'s `SKILLS` dict (e.g. `Python, SQL, Machine Learning`).
2. Go to the homepage, click "Apply", upload any PDF resume.
3. See your `screening_score`; if it clears the threshold, take the MCQ.
4. Submit — see `mcq_score`, `final_score`, `final_recommendation`.

## Your dataset — what's wired in vs. what's just bundled

`backend/data/` now has your real CSVs. Two of them are actively loaded by
the app at startup:

- **`01_skill_taxonomy.csv`** → `matcher.py::_load_taxonomy()` builds `SKILLS`,
  `FUZZY_VARIANTS`, `CONTEXTUAL_PHRASES` from it directly (50 skills, 5
  categories, matching your real taxonomy instead of the small hardcoded set).
- **`06_mcq_bank.csv`** → `matcher.py::_load_mcq_bank()` loads all 27
  questions. Note this file's `correct_option` is a letter (`a`/`b`/`c`/`d`)
  pointing at the `option_a`–`option_d` columns, not the answer text itself —
  `generate_mcq()` resolves that letter to the actual text before building
  the server-side answer key, so grading still compares text-to-text.

**`02_resumes.csv`, `03_job_descriptions.csv`, `04_gold_match_pairs.csv`,
`05_fraud_dataset.csv` are copied into `backend/data/` but not loaded by any
endpoint yet.** They're not resume PDFs, so they can't go through
`/applications/apply` as-is. If you want to use them for testing:

- **Quick manual test:** paste a `resume_text` value from `02_resumes.csv`
  and a `jd_text` value from `03_job_descriptions.csv` into a small Python
  snippet calling `matcher.score_application(resume_text, jd_text,
  required_skills)` directly — no need to go through the API or a PDF at all.
- **Full seeding:** I can add a one-off script that reads
  `03_job_descriptions.csv` and inserts each row as a `JobPosting`, so they
  show up in the frontend's job list ready to apply against with a real PDF.
  Ask if you want that added.
- **Threshold tuning:** `04_gold_match_pairs.csv`'s `gold_match_score` /
  `gold_match_tier` columns are exactly what you'd compare
  `matcher.score_application()`'s output against to check whether the 0.70/0.30
  weights and 40/70 tier cutoffs need adjusting for your data.
- **Fraud check:** `05_fraud_dataset.csv` has paired `genuine_resume_text` /
  `stuffed_resume_text` with `injected_skills` labeled — run both through
  `score_application()` with the same JD and confirm the screening scores
  land close together, then run the MCQ layer on the stuffed one's claimed
  skills and confirm it's the injected skills specifically that get missed.

## 6. Real-time email notifications

When a candidate applies, the backend sends an email in the background
(doesn't block the API response):

- **Score ≥ threshold ("invited"):** email with the score, a single-use MCQ
  link, its expiry time, and the list of claimed skills to prepare for
  (exactly what the quiz will test).
- **Score < threshold ("rejected"):** email with the score, the threshold,
  and the specific required skills missing from the resume.

**Setup:** copy `backend/.env.example` → `backend/.env` and fill in:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
FROM_EMAIL=your_email@gmail.com
FRONTEND_URL=http://localhost:3000
```

For Gmail: enable 2-Step Verification on the account, then generate an **App
Password** at myaccount.google.com/apppasswords — your regular Gmail
password won't work for SMTP. Any other SMTP provider (Outlook, SendGrid,
Mailtrap for testing without hitting real inboxes) works the same way, just
change `SMTP_HOST`/`SMTP_PORT`.

**If you don't configure SMTP:** `email_service.py` detects the missing
credentials and prints the email content to the console instead of failing
— so the apply/screening flow still works end-to-end without email set up,
you just won't get a real inbox notification.

## 7. Testing all resumes against the synthetic dataset (for your paper)

`backend/evaluate_dataset.py` runs the scoring pipeline directly against
your CSVs — no API, no Postgres, no PDF uploads. It's the fast path to
actual numbers for your Results section.

```powershell
cd backend
venv\Scripts\activate
python evaluate_dataset.py
```

This produces `backend/eval_results/`:

- **`gold_pair_results.csv`** — your `S1` vs. the dataset's
  `gold_match_score` for all 250 gold pairs, plus tier agreement. Console
  output gives you the Pearson correlation and tier-accuracy numbers
  directly — these are your headline "how well does the hybrid score track
  gold judgments" results.
- **`skill_cascade_results.csv`** — every labeled skill in all 500 resumes,
  your cascade's predicted tier vs. the dataset's ground-truth
  `skill_mention_types`. Console output gives per-tier recall (exact/fuzzy/
  contextual) — this is your cascade accuracy result.
- **`fraud_detection_results.csv`** — all 150 genuine/stuffed pairs, their
  score difference, and which injected skills passed screening undetected.
  Console output gives the average score difference (should be near zero —
  that's what proves screening alone is gameable) and the injected-skill
  pass-through rate (the population your MCQ layer needs to catch).

Runtime note: this uses the real SBERT model locally on 500+250+150 texts,
so expect a few minutes on a laptop CPU.

**Turning this into your fraud-detection headline number:** the script
tells you *which* injected skills passed screening per fraud pair
(`injected_skills_that_passed_screening` column). To get your final
end-to-end fraud-catch rate, feed those specific skills through
`matcher.generate_mcq()` / `matcher.grade_mcq()` for each pair and report
what fraction get answered wrong — that's the number showing your
closed-loop system catches what screening alone misses. Ask if you want
this folded directly into the script.

## 8. Known simplifications (vs a production system)

- No HR authentication — anyone can post jobs.
- Fuzzy matching uses Python's stdlib `difflib` instead of
  `python-Levenshtein`, so there's no C-compiler dependency on Windows — the
  logic and 0.82 threshold are the same idea, just a different ratio
  implementation.
- Resume files are saved to `backend/uploads/` on local disk, unencrypted.
