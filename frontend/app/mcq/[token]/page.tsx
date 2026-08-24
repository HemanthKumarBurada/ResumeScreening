"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Question = { id: string; skill: string; question: string; options: string[] };

export default function McqPage() {
  const { token } = useParams<{ token: string }>();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  // Timer State (150 seconds = 2:30)
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const hasSubmitted = useRef(false);

  // 1. Fetch Questions and initialize the timer
  useEffect(() => {
    fetch(`${API}/applications/mcq/${token}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then((data) => {
        setQuestions(data.questions);
        setTimeLeft(data.total_time_seconds || 150);
      })
      .catch((err) => setError(err.message || "This link is invalid or has expired"))
      .finally(() => setLoading(false));
  }, [token]);

  // 2. Timer Logic
  useEffect(() => {
    if (timeLeft === null || hasSubmitted.current || error || result) return;

    if (timeLeft <= 0) {
      handleSubmit();
      return;
    }

    const timerId = setInterval(() => {
      setTimeLeft((prev) => (prev !== null ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(timerId);
  }, [timeLeft, error, result]);

  // 3. Browser Anti-Cheat (Tab switching & Right-click prevention)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && !hasSubmitted.current && !result && !error) {
        alert("WARNING: You left the test tab. This action has been recorded.");
      }
    };

    const handleContext = (e: MouseEvent) => e.preventDefault(); // Disable Right-Click

    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("contextmenu", handleContext);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("contextmenu", handleContext);
    };
  }, [result, error]);

  // Format seconds into MM:SS for display
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  async function handleSubmit() {
    if (hasSubmitted.current) return;
    hasSubmitted.current = true;
    
    setSubmitting(true);
    try {
      const payload = Object.entries(answers).map(([question_id, selected_option]) => ({ question_id, selected_option }));
      const res = await fetch(`${API}/applications/mcq/${token}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err: any) {
      setError(err.message || "Could not submit answers");
      hasSubmitted.current = false; // allow retry on error
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Loading assessment...</p>;
  if (error) return <div className="error-box">{error}</div>;

  if (result) {
    return (
      <main>
        <h1>Assessment Complete</h1>
        <div className="card">
          <p>MCQ score: <strong>{result.mcq_score}</strong> / 100</p>
          <p>Final combined score: <strong>{result.final_score}</strong> / 100</p>
          <p>
            Recommendation:{" "}
            <span className={`badge badge-${result.final_recommendation?.toLowerCase()}`}>
              {result.final_recommendation}
            </span>
          </p>
          {result.cheating_flag && (
            <p style={{ color: "red", fontWeight: "bold", marginTop: "1rem" }}>
              {result.cheating_flag}
            </p>
          )}
        </div>
      </main>
    );
  }

  return (
    // Anti-cheat: Disable text selection and copying
    <main 
      style={{ userSelect: "none" }} 
      onCopy={(e) => {
        e.preventDefault();
        alert("Copying is disabled during the assessment.");
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Skills Assessment</h1>
        
        {timeLeft !== null && (
          <div style={{
            fontSize: '1.2rem',
            fontWeight: 'bold',
            color: timeLeft <= 30 ? 'red' : 'inherit',
            padding: '10px',
            border: `2px solid ${timeLeft <= 30 ? 'red' : '#ddd'}`,
            borderRadius: '8px'
          }}>
            ⏱ Time Remaining: {formatTime(timeLeft)}
          </div>
        )}
      </div>
      
      <p className="subtitle">This link is single-use — submit when you're ready.</p>

      {questions.map((q, i) => (
        <div key={q.id} className="card">
          <p style={{ marginTop: 0 }}>
            <span className="skill-tag skill-tag-claimed">{q.skill}</span>
          </p>
          <p><strong>Q{i + 1}.</strong> {q.question}</p>
          {q.options.map((opt) => (
            <label key={opt} style={{ display: "block", padding: "4px 0", cursor: "pointer" }}>
              <input
                type="radio"
                name={q.id}
                value={opt}
                checked={answers[q.id] === opt}
                onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
              /> {opt}
            </label>
          ))}
        </div>
      ))}

      {questions.length > 0 && (
        <button onClick={handleSubmit} disabled={submitting || timeLeft === 0}>
          {submitting && <span className="spinner" />}
          {submitting ? "Submitting..." : "Submit Answers"}
        </button>
      )}
    </main>
  );
}