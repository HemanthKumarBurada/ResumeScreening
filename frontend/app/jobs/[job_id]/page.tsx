"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Candidate = {
  application_id: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  screening_score: number;
  mcq_score: number | null;
  final_score: number | null;
  recommendation: string | null;
};

export default function HrRankingPage() {
  const { job_id } = useParams<{ job_id: string }>();
  const [jobTitle, setJobTitle] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/jobs/${job_id}/candidates`)
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then((data) => {
        setJobTitle(data.job_title);
        setCandidates(data.candidates);
      })
      .catch((err) => setError(err.message || "Failed to load candidates"))
      .finally(() => setLoading(false));
  }, [job_id]);

  if (loading) return <p>Loading rankings...</p>;
  if (error) return <div className="error-box">{error}</div>;

  return (
    <main style={{ padding: "2rem", maxWidth: "1000px", margin: "0 auto" }}>
      <h1>Candidate Rankings</h1>
      <h2 className="subtitle" style={{ marginBottom: "2rem" }}>{jobTitle}</h2>

      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #ddd" }}>
            <th style={{ padding: "12px 8px" }}>Rank</th>
            <th style={{ padding: "12px 8px" }}>Candidate</th>
            <th style={{ padding: "12px 8px" }}>Status</th>
            <th style={{ padding: "12px 8px" }}>Screening Score</th>
            <th style={{ padding: "12px 8px" }}>MCQ Score</th>
            <th style={{ padding: "12px 8px" }}>Final Score</th>
            <th style={{ padding: "12px 8px" }}>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, index) => (
            <tr key={c.application_id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: "12px 8px", fontWeight: "bold" }}>#{index + 1}</td>
              <td style={{ padding: "12px 8px" }}>
                <div>{c.candidate_name}</div>
                <div style={{ fontSize: "0.85em", color: "var(--muted)" }}>{c.candidate_email}</div>
              </td>
              <td style={{ padding: "12px 8px" }}>
                <span className={`badge badge-${c.status}`}>{c.status}</span>
              </td>
              <td style={{ padding: "12px 8px" }}>{c.screening_score?.toFixed(1)}</td>
              <td style={{ padding: "12px 8px" }}>{c.mcq_score !== null ? c.mcq_score.toFixed(1) : "—"}</td>
              <td style={{ padding: "12px 8px", fontWeight: "bold" }}>
                {c.final_score !== null ? c.final_score.toFixed(1) : "—"}
              </td>
              <td style={{ padding: "12px 8px" }}>
                {c.recommendation ? (
                  <span className={`badge badge-${c.recommendation.toLowerCase()}`}>
                    {c.recommendation}
                  </span>
                ) : "—"}
              </td>
            </tr>
          ))}
          {candidates.length === 0 && (
            <tr>
              <td colSpan={7} style={{ padding: "2rem", textAlign: "center", color: "#666" }}>
                No candidates have applied for this role yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}