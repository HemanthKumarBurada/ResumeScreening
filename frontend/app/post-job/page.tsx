"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CATEGORIES = ["Data Science", "Web Development", "DevOps", "Human Resources", "Finance"];

export default function PostJobPage() {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");
  const [threshold, setThreshold] = useState(60);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("category", category);
      form.append("description", description);
      form.append("required_skills", skills);
      form.append("min_screening_threshold", String(threshold));

      const res = await fetch(`${API}/jobs`, { method: "POST", body: form });
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
      <h1>Post a Job</h1>
      <p className="subtitle">Skills must match your taxonomy's canonical names exactly.</p>

      <form onSubmit={handleSubmit} className="card card-list">
        <label className="field">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="field">
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} required rows={5} />
        </label>
        <label className="field">
          Required skills (comma-separated, e.g. Python, SQL, Machine Learning)
          <input value={skills} onChange={(e) => setSkills(e.target.value)} required />
        </label>
        <label className="field">
          Minimum screening threshold (0-100)
          <input type="number" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
        </label>
        <button type="submit" disabled={loading}>
          {loading && <span className="spinner" />}
          {loading ? "Posting..." : "Post Job"}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="card">
          <p><strong>{result.title}</strong> posted successfully.</p>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Job ID: {result.id}</p>
        </div>
      )}
    </main>
  );
}
