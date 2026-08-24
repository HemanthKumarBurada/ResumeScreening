"""
Sends the screening-result notification emails:
  - Qualified: score, and which required skills the resume matched.
  - Rejected: score, and which required skills were missing from the resume.

Uses plain smtplib so it works with any SMTP provider (Gmail with an App
Password, Outlook, SendGrid's SMTP relay, Mailtrap for testing, etc.) --
no extra service to sign up for beyond picking one and putting its
credentials in .env.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def _send(to_email: str, subject: str, html_body: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[email_service] SMTP not configured -- skipping send to {to_email}. "
              f"Set SMTP_USER/SMTP_PASSWORD in .env to enable real emails.")
        print(f"[email_service] Would have sent:\nSubject: {subject}\n{html_body}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        print(f"[email_service] Sent '{subject}' to {to_email}")
    except Exception as e:
        # Never let an email failure break the applicant's submission flow.
        print(f"[email_service] Failed to send email to {to_email}: {e}")


def send_qualified_email(
    to_email: str,
    candidate_name: str,
    job_title: str,
    screening_score: float,
    claimed_skills: list[str],
):
    skills_list = "".join(f"<li>{s}</li>" for s in claimed_skills) or "<li>General role fundamentals</li>"

    subject = f"You're invited to the next round — {job_title}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px;">
      <h2>Congratulations, {candidate_name}!</h2>
      <p>Your application for <strong>{job_title}</strong> scored
         <strong>{screening_score}/100</strong> in our initial screening,
         which clears the threshold for this role.</p>
      <p>Our team will be in touch about next steps. Skills your resume
         matched against this role:</p>
      <ul>{skills_list}</ul>
      <p>Good luck!</p>
    </div>
    """
    _send(to_email, subject, html)


def send_rejected_email(
    to_email: str,
    candidate_name: str,
    job_title: str,
    screening_score: float,
    threshold: float,
    missing_skills: list[str],
):
    missing_list = "".join(f"<li>{s}</li>" for s in missing_skills) or "<li>No specific gaps detected — score was borderline overall</li>"

    subject = f"Update on your application — {job_title}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px;">
      <h2>Hi {candidate_name},</h2>
      <p>Thank you for applying to <strong>{job_title}</strong>. Your resume
         scored <strong>{screening_score}/100</strong> against a screening
         threshold of <strong>{threshold}/100</strong> for this role, so we
         won't be moving forward at this time.</p>
      <p>Based on our screening, these required skills weren't clearly
         reflected in your resume — consider highlighting or building
         experience in these areas before reapplying:</p>
      <ul>{missing_list}</ul>
      <p>We encourage you to apply again for future roles that better match
         your current skill set.</p>
    </div>
    """
    _send(to_email, subject, html)