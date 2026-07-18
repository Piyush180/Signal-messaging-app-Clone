"use client";

// Two-step mocked auth: enter phone -> we "send" a demo OTP -> enter code.
// The demo OTP is shown on screen because this is a portfolio/demo build.

import { useState } from "react";
import { Lock } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export function AuthScreen() {
  const { login } = useAuth();
  const [step, setStep] = useState<1 | 2>(1);
  const [phone, setPhone] = useState("+15551234567");
  const [code, setCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.requestOtp(phone.trim());
      setCode(res.otp_demo); // prefill for the demo
      setNotice(`Demo code: ${res.otp_demo}`);
      setStep(2);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(phone.trim(), code.trim(), fullName.trim() || undefined);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center-screen">
      <div className="modal" style={{ width: 380, textAlign: "center" }}>
        <div
          style={{
            width: 64, height: 64, borderRadius: "50%", background: "var(--bg-active)",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            marginBottom: 12,
          }}
        >
          <Lock size={30} color="var(--signal-blue)" />
        </div>
        <h2 style={{ marginBottom: 6 }}>Signal Clone</h2>
        <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 20 }}>
          Real-time messaging demo. Sign in with a phone number.
        </p>

        {error && <div className="alert-error">{error}</div>}
        {notice && <div className="alert-ok">{notice}</div>}

        {step === 1 ? (
          <form onSubmit={requestOtp}>
            <div className="field" style={{ textAlign: "left" }}>
              <label>Phone number</label>
              <input
                className="input"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+15551234567"
                required
              />
            </div>
            <button className="btn" disabled={busy}>
              {busy ? "Sending…" : "Send code"}
            </button>
          </form>
        ) : (
          <form onSubmit={verify}>
            <div className="field" style={{ textAlign: "left" }}>
              <label>Verification code</label>
              <input
                className="input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                required
              />
            </div>
            <div className="field" style={{ textAlign: "left" }}>
              <label>Name (only for a new account)</label>
              <input
                className="input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alice Smith"
              />
            </div>
            <button className="btn" disabled={busy}>
              {busy ? "Verifying…" : "Verify & continue"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              style={{ marginTop: 8 }}
              onClick={() => { setStep(1); setNotice(""); }}
            >
              Change number
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
