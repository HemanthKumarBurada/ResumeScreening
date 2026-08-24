import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import JobPosting, Candidate, Application
import matcher
import email_service
from document_extractor import extract_text

Base.metadata.create_all(bind=engine)  # creates tables on first run if they don't exist

app = FastAPI(title="ATS - Closed Loop Resume Screening")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.post("/jobs")
def create_job(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    required_skills: str = Form(..., description="comma-separated, e.g. Python,SQL"),
    min_screening_threshold: float = Form(60.0),
    db: Session = Depends(get_db),
):
    skills = [s.strip() for s in required_skills.split(",") if s.strip()]
    job = JobPosting(
        title=title,
        category=category,
        description=description,
        required_skills=skills,
        min_screening_threshold=min_screening_threshold,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return db.query(JobPosting).order_by(JobPosting.created_at.desc()).all()


@app.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ---------------------------------------------------------------------------
# Applications - upload resume, get scored (S1), status set based on threshold
# ---------------------------------------------------------------------------

@app.post("/applications/apply")
async def apply(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    candidate_email: str = Form(...),
    candidate_name: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    # Accept PDF, Word, and image files
    allowed_content_types = {
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
    }
    
    # Get file extension from content type or filename
    file_ext = allowed_content_types.get(resume.content_type)
    if not file_ext:
        # Try to infer from filename
        filename_lower = resume.filename.lower()
        if filename_lower.endswith(('.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif')):
            file_ext = Path(resume.filename).suffix
        else:
            raise HTTPException(400, "Only PDF, DOCX, DOC, JPG, PNG, TIFF files are accepted")
    
    file_bytes = await resume.read()
    orig_filename = resume.filename or f"resume{file_ext}"
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join("uploads", filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    
    # Extract text using universal extractor
    try:
        resume_text = extract_text(file_bytes, orig_filename)
    except ValueError as e:
        raise HTTPException(422, f"Could not extract text from document: {str(e)}")

    candidate = db.query(Candidate).filter(Candidate.email == candidate_email).first()
    if not candidate:
        candidate = Candidate(email=candidate_email, full_name=candidate_name)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

    result = matcher.score_application(resume_text, job.description, job.required_skills)

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_path=filepath,
        extracted_skills=result["skill_matches"],
        semantic_similarity=result["phi_sem"],
        skill_match_ratio=result["theta_skill"],
        screening_score=result["screening_score"],
    )

    passes = result["screening_score"] >= job.min_screening_threshold
    application.screening_status = "invited" if passes else "rejected"
    db.add(application)
    db.commit()
    db.refresh(application)

    missing_skills = [m["skill"] for m in result["skill_matches"] if m["weight"] == 0]
    claimed_skills = [m["skill"] for m in result["skill_matches"] if m["weight"] > 0]

    if passes:
        background_tasks.add_task(
            email_service.send_qualified_email,
            to_email=candidate.email,
            candidate_name=candidate.full_name,
            job_title=job.title,
            screening_score=application.screening_score,
            claimed_skills=claimed_skills,
        )
    else:
        background_tasks.add_task(
            email_service.send_rejected_email,
            to_email=candidate.email,
            candidate_name=candidate.full_name,
            job_title=job.title,
            screening_score=application.screening_score,
            threshold=job.min_screening_threshold,
            missing_skills=missing_skills,
        )

    return {
        "id": application.id,
        "screening_score": application.screening_score,
        "phi_sem": application.semantic_similarity,
        "theta_skill": application.skill_match_ratio,
        "screening_status": application.screening_status,
        "missing_skills": missing_skills,
        "claimed_skills": claimed_skills,
    }


@app.get("/jobs/{job_id}/candidates")
def get_job_candidates(job_id: str, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    # Fetch all applications for this job
    applications = db.query(Application).filter(Application.job_id == job_id).all()

    # Sort applications: highest screening_score first
    ranked_applications = sorted(
        applications,
        key=lambda app: app.screening_score if app.screening_score is not None else -1.0,
        reverse=True,
    )

    results = []
    for application in ranked_applications:
        results.append({
            "application_id": application.id,
            "candidate_name": application.candidate.full_name,
            "candidate_email": application.candidate.email,
            "status": application.screening_status,
            "screening_score": application.screening_score,
            "applied_at": application.created_at.isoformat()
        })

    return {
        "job_title": job.title,
        "candidates": results
    }



@app.get("/applications/{application_id}")
def get_application(application_id: str, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Not found")
    return application


@app.get("/health")
def health():
    return {"status": "ok"}