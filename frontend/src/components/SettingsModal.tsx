"use client";

import { useEffect, useState } from "react";
import { Bell, Laptop, Moon, ShieldCheck, Sun, X } from "lucide-react";
import { api } from "@/lib/api";
import { THEME_KEY } from "@/lib/config";
import { useAuth } from "@/context/AuthContext";
import { Avatar } from "./Avatar";

interface Props {
  onClose: () => void;
}

export function SettingsModal({ onClose }: Props) {
  const { user, setUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? "");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [ok, setOk] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = (localStorage.getItem(THEME_KEY) as "light" | "dark") || "light";
    setTheme(t);
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem(THEME_KEY, next);
    document.documentElement.setAttribute("data-theme", next);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setOk(false);
    try {
      const updated = await api.updateProfile({
        full_name: fullName,
        bio,
        avatar_url: avatarUrl,
      });
      setUser(updated);
      setOk(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        {error && <div className="alert-error">{error}</div>}
        {ok && <div className="alert-ok">Profile saved.</div>}

        <div style={{ textAlign: "center", marginBottom: 16 }}>
          <Avatar name={fullName || user?.full_name} id={user?.id} url={avatarUrl} size={72} />
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
            {user?.phone_number}
          </div>
        </div>

        <form onSubmit={save}>
          <div className="field">
            <label>Display name</label>
            <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="field">
            <label>About</label>
            <input className="input" value={bio} onChange={(e) => setBio(e.target.value)}
              placeholder="A short status" />
          </div>
          <div className="field">
            <label>Avatar image URL</label>
            <input className="input" value={avatarUrl} onChange={(e) => setAvatarUrl(e.target.value)}
              placeholder="https://…" />
          </div>
          <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </form>

        {/* Appearance */}
        <div className="field" style={{ marginTop: 18 }}>
          <label>Appearance</label>
          <button className="btn btn-ghost" onClick={toggleTheme}>
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            <span style={{ marginLeft: 8 }}>
              {theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            </span>
          </button>
        </div>

        {/* Placeholder sections required by the brief */}
        <div className="field">
          <label>Privacy &amp; notifications</label>
          <div className="list-row"><div className="who"><Bell size={16} /> Notifications</div><span style={{ color: "var(--text-muted)", fontSize: 12 }}>Coming soon</span></div>
          <div className="list-row"><div className="who"><ShieldCheck size={16} /> Safety number</div><span style={{ color: "var(--text-muted)", fontSize: 12 }}>Coming soon</span></div>
          <div className="list-row"><div className="who"><Laptop size={16} /> Linked devices</div><span style={{ color: "var(--text-muted)", fontSize: 12 }}>Coming soon</span></div>
        </div>
      </div>
    </div>
  );
}
