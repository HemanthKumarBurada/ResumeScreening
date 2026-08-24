"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export default function ApplyPage() {
  const { jobId } =
    useParams<{ jobId: string }>();

  const [job, setJob] = useState<any>(null);

  const [candidateName, setCandidateName] =
    useState("");

  const [candidateEmail, setCandidateEmail] =
    useState("");

  const [resume, setResume] =
    useState<File | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const [result, setResult] =
    useState<any>(null);

  useEffect(() => {
    if (!jobId) return;

    async function loadJob() {
      try {
        const response = await fetch(
          `${API}/jobs/${jobId}`
        );

        if (!response.ok) {
          throw new Error(
            await response.text()
          );
        }

        const data =
          await response.json();

        setJob(data);
      } catch (err: any) {
        setError(
          err.message ||
            "Failed to load job"
        );
      }
    }

    loadJob();
  }, [jobId]);

  async function handleSubmit(
    e: React.FormEvent
  ) {
    e.preventDefault();

    setError("");
    setResult(null);

    if (!resume) {
      setError(
        "Please upload your resume."
      );
      return;
    }

    setLoading(true);

    try {
      const form = new FormData();

      form.append("job_id", jobId);
      form.append(
        "candidate_name",
        candidateName
      );
      form.append(
        "candidate_email",
        candidateEmail
      );
      form.append("resume", resume);

      const response = await fetch(
        `${API}/applications/apply`,
        {
          method: "POST",
          body: form,
        }
      );

      if (!response.ok) {
        throw new Error(
          await response.text()
        );
      }

      const data =
        await response.json();

      setResult(data);
    } catch (err: any) {
      setError(
        err.message ||
          "Application failed"
      );
    } finally {
      setLoading(false);
    }
  }

  if (error && !job) {
    return (
      <main>
        <div className="error-box">
          {error}
        </div>
      </main>
    );
  }

  if (!job) {
    return (
      <main>
        <p>Loading job...</p>
      </main>
    );
  }

  return (
    <main>
      {!result ? (
        <>
          <h1>Apply for {job.title}</h1>

          <p className="subtitle">
            {job.category}
          </p>

          <div className="card">
            <h2>Job Description</h2>

            <p>
              {job.description}
            </p>

            {job.required_skills && (
              <div
                style={{
                  marginTop: "1rem",
                }}
              >
                <strong>
                  Required Skills
                </strong>

                <div
                  style={{
                    marginTop: "8px",
                  }}
                >
                  {job.required_skills.map(
                    (skill: string) => (
                      <span
                        key={skill}
                        className="skill-tag"
                        style={{
                          marginRight: 6,
                        }}
                      >
                        {skill}
                      </span>
                    )
                  )}
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={handleSubmit}
            className="card card-list"
          >
            <h2>
              Candidate Information
            </h2>

            <label className="field">
              Full Name

              <input
                type="text"
                value={candidateName}
                onChange={(e) =>
                  setCandidateName(
                    e.target.value
                  )
                }
                required
              />
            </label>

            <label className="field">
              Email

              <input
                type="email"
                value={candidateEmail}
                onChange={(e) =>
                  setCandidateEmail(
                    e.target.value
                  )
                }
                placeholder="you@example.com"
                required
              />

              <span
                style={{
                  fontSize: "0.85rem",
                  color: "var(--muted)",
                }}
              >
                Your application result
                will be sent to this email.
              </span>
            </label>

            <label className="field">
              Resume

              <input
                type="file"
                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.tiff"
                onChange={(e) =>
                  setResume(
                    e.target.files?.[0] ||
                      null
                  )
                }
                required
              />

              <span
                style={{
                  fontSize: "0.85rem",
                  color: "var(--muted)",
                }}
              >
                Accepted formats:
                PDF, DOC, DOCX, JPG,
                PNG, TIFF
              </span>
            </label>

            {error && (
              <div className="error-box">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
            >
              {loading && (
                <span className="spinner" />
              )}

              {loading
                ? "Screening Resume..."
                : "Submit Application"}
            </button>
          </form>
        </>
      ) : (
        <div
          className="card"
          style={{
            textAlign: "center",
            padding: "3rem 2rem",
            maxWidth: "700px",
            margin: "3rem auto",
          }}
        >
          <h1>
            Application Submitted
          </h1>

          <p
            style={{
              marginTop: "1.5rem",
              fontSize: "1.1rem",
            }}
          >
            Thank you for applying for{" "}
            <strong>
              {job.title}
            </strong>
            .
          </p>

          <p
            style={{
              marginTop: "1rem",
              fontSize: "1rem",
            }}
          >
            We have emailed your
            application result to:
          </p>

          <p
            style={{
              marginTop: "0.5rem",
              fontSize: "1.1rem",
              fontWeight: "bold",
            }}
          >
            {candidateEmail}
          </p>

          <p
            style={{
              marginTop: "1.5rem",
              color: "var(--muted)",
              fontSize: "0.9rem",
            }}
          >
            Please check your inbox and
            spam folder for further
            information.
          </p>
        </div>
      )}
    </main>
  );
}