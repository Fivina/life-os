import { ArrowRight } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { hasSupabaseConfig, signInWithPassword } from "../../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const supabaseConfigured = hasSupabaseConfig();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "signing-in" | "error">("idle");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("signing-in");
    try {
      await signInWithPassword(email, password);
      navigate("/", { replace: true });
    } catch {
      setStatus("error");
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark">LO</div>
        <p className="eyebrow">Private foundation</p>
        <h1 id="login-title">Life OS</h1>
        <form onSubmit={handleSubmit} className="login-form">
          {supabaseConfigured ? (
            <>
              <label>
                Email
                <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </label>
              <label>
                Password
                <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
              </label>
            </>
          ) : (
            <label>
              Access mode
              <input value="Development mode" readOnly />
            </label>
          )}
          <button className="primary-button" type="submit" disabled={status === "signing-in"}>
            <span>{status === "signing-in" ? "Signing in" : "Enter"}</span>
            <ArrowRight size={18} aria-hidden="true" />
          </button>
          {status === "error" ? <p className="status-text error">Sign in failed.</p> : null}
        </form>
      </section>
    </main>
  );
}
