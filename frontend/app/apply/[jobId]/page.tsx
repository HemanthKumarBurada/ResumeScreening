"use client";

import { useState } from "react";
import { useParams } from "next/navigation";


const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ApplyPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!resume) return;
    setLoading(true);

    try {
      const form = new FormData();
      form.append("job_id", jobId);
      form.append("candidate_email", email);
      form.append("candidate_name", name);
      form.append("resume", resume);

      const res = await fetch(`${API}/applications/apply`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Apply</h1>
      <p className="subtitle">Upload your resume in any format (PDF, Word, or Image) — you'll get an instant screening result and an email notification.</p>

      <form onSubmit={handleSubmit} className="card card-list">
        <label className="field">
          Full name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="field">
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          Resume (PDF, Word, or Image)
          <input 
            type="file" 
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.tiff,.bmp,.gif,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png,image/tiff,image/bmp,image/gif" 
            onChange={(e) => setResume(e.target.files?.[0] || null)} 
            required 
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading && <span className="spinner" />}
          {loading ? "Scoring your resume..." : "Submit Application"}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

     {result && (
  <div className="card">
    <h2 style={{ marginTop: 0 }}>Application Submitted</h2>
    <p>Thanks for applying — we've emailed you the result of your screening at <strong>{email}</strong>.</p>
    <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
      If you qualified, check your inbox for a secure, time-limited link to the skills assessment.
    </p>
  </div>
)}
    </main>
  );
}
