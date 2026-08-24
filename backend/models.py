import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    required_skills = Column(JSON, nullable=False)          # ["Python", "SQL", ...]
    min_screening_threshold = Column(Float, default=60.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    applications = relationship("Application", back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    applications = relationship("Application", back_populates="candidate")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=False), ForeignKey("job_postings.id"))
    candidate_id = Column(UUID(as_uuid=False), ForeignKey("candidates.id"))

    resume_path = Column(String, nullable=False)
    extracted_skills = Column(JSON)          # [{"skill": "Python", "tier": "exact", "weight": 1.0}, ...]
    semantic_similarity = Column(Float)      # Phi_sem
    skill_match_ratio = Column(Float)        # Theta_skill
    screening_score = Column(Float)          # S1
    screening_status = Column(String, default="pending")  # pending | invited | rejected

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("JobPosting", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")