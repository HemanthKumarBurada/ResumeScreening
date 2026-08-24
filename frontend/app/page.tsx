import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function HomePage() {
  const jobs = await fetch(`${API}/jobs`, { cache: "no-store" })
    .then((r) => r.json())
    .catch(() => []);

  return (
    <main>
      <h1>Open Positions</h1>
      <p className="subtitle">Browse roles and apply with your resume.</p>

      <div className="card">
        {jobs.length === 0 && <p style={{ color: "var(--muted)" }}>No jobs posted yet.</p>}
        {jobs.map((job: any) => (
          <div key={job.id} className="job-item">
            <strong>{job.title}</strong>
            <span className="skill-tag" style={{ marginLeft: 8 }}>{job.category}</span>
            <div style={{ marginTop: 6 }}>
              <Link href={`/apply/${job.id}`}>Apply with resume →</Link>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
