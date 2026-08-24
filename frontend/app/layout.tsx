import "./globals.css";
import Link from "next/link";

export const metadata = { title: "ATS", description: "Closed-loop resume screening" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 24px" }}>
          <div className="nav-bar">
            <Link href="/" style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text)" }}>
              ATS
            </Link>
            <Link href="/post-job">Post a job (HR)</Link>
          </div>
          {children}
        </div>
      </body>
    </html>
  );
}
