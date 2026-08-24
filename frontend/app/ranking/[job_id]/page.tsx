"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const BEST_CUT = 65;
const AVERAGE_CUT = 40;

type Candidate = {
  application_id: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  screening_score: number | null;
  applied_at: string;
};

function getTier(score: number | null) {
  if (score === null) {
    return "Low";
  }

  if (score >= BEST_CUT) {
    return "Best";
  }

  if (score >= AVERAGE_CUT) {
    return "Average";
  }

  return "Low";
}

export default function HrRankingPage() {
  const { job_id } =
    useParams<{ job_id: string }>();

  const [jobTitle, setJobTitle] =
    useState("");

  const [candidates, setCandidates] =
    useState<Candidate[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    if (!job_id) return;

    async function loadCandidates() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `${API}/jobs/${job_id}/candidates`
        );

        if (!response.ok) {
          throw new Error(
            await response.text()
          );
        }

        const data =
          await response.json();

        setJobTitle(data.job_title);
        setCandidates(data.candidates);
      } catch (err: any) {
        setError(
          err.message ||
            "Failed to load candidates"
        );
      } finally {
        setLoading(false);
      }
    }

    loadCandidates();
  }, [job_id]);

  if (loading) {
    return (
      <main>
        <p>Loading rankings...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main>
        <div className="error-box">
          {error}
        </div>
      </main>
    );
  }

  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: "1100px",
        margin: "0 auto",
      }}
    >
      <h1>Candidate Rankings</h1>

      <h2
        className="subtitle"
        style={{
          marginBottom: "1rem",
        }}
      >
        {jobTitle}
      </h2>

      <p
        style={{
          color: "var(--muted)",
          marginBottom: "2rem",
        }}
      >
        Ranking is based on screening score.
        Tier: Best ≥ {BEST_CUT}, Average ≥{" "}
        {AVERAGE_CUT}, Low &lt; {AVERAGE_CUT}.
      </p>

      <div className="card">
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
          }}
        >
          <thead>
            <tr
              style={{
                borderBottom:
                  "2px solid #ddd",
              }}
            >
              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Rank
              </th>

              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Candidate
              </th>

              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Status
              </th>

              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Screening Score
              </th>

              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Tier
              </th>

              <th
                style={{
                  padding: "12px 8px",
                }}
              >
                Applied At
              </th>
            </tr>
          </thead>

          <tbody>
            {candidates.map(
              (candidate, index) => {
                const tier = getTier(
                  candidate.screening_score
                );

                return (
                  <tr
                    key={
                      candidate.application_id
                    }
                    style={{
                      borderBottom:
                        "1px solid #eee",
                    }}
                  >
                    <td
                      style={{
                        padding: "12px 8px",
                        fontWeight: "bold",
                      }}
                    >
                      #{index + 1}
                    </td>

                    <td
                      style={{
                        padding: "12px 8px",
                      }}
                    >
                      <div>
                        {
                          candidate.candidate_name
                        }
                      </div>

                      <div
                        style={{
                          fontSize: "0.85em",
                          color:
                            "var(--muted)",
                        }}
                      >
                        {
                          candidate.candidate_email
                        }
                      </div>
                    </td>

                    <td
                      style={{
                        padding: "12px 8px",
                      }}
                    >
                      <span
                        className={`badge badge-${candidate.status}`}
                      >
                        {
                          candidate.status
                        }
                      </span>
                    </td>

                    <td
                      style={{
                        padding: "12px 8px",
                        fontWeight: "bold",
                      }}
                    >
                      {candidate.screening_score !==
                      null
                        ? candidate.screening_score.toFixed(
                            1
                          )
                        : "—"}
                    </td>

                    <td
                      style={{
                        padding: "12px 8px",
                      }}
                    >
                      <span
                        className={`badge badge-${tier.toLowerCase()}`}
                      >
                        {tier}
                      </span>
                    </td>

                    <td
                      style={{
                        padding: "12px 8px",
                        color:
                          "var(--muted)",
                      }}
                    >
                      {new Date(
                        candidate.applied_at
                      ).toLocaleString()}
                    </td>
                  </tr>
                );
              }
            )}

            {candidates.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  style={{
                    padding: "2rem",
                    textAlign: "center",
                    color: "#666",
                  }}
                >
                  No candidates have
                  applied for this role
                  yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}