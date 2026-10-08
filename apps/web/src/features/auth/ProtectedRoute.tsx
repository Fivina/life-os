import { Navigate, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";

import { restoreSession } from "../../lib/auth";

export function ProtectedRoute() {
  const [state, setState] = useState<"checking" | "signed-in" | "signed-out">("checking");

  useEffect(() => {
    let active = true;
    restoreSession()
      .then((ok) => {
        if (active) {
          setState(ok ? "signed-in" : "signed-out");
        }
      })
      .catch(() => {
        if (active) {
          setState("signed-out");
        }
      });
    function handleExpired() {
      setState("signed-out");
    }
    window.addEventListener("life-os:auth-expired", handleExpired);
    return () => {
      active = false;
      window.removeEventListener("life-os:auth-expired", handleExpired);
    };
  }, []);

  if (state === "checking") {
    return (
      <main className="login-page">
        <section className="login-panel">
          <p className="eyebrow">Checking session</p>
          <h1>Life OS</h1>
        </section>
      </main>
    );
  }

  if (state === "signed-out") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
