"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact, Conversation } from "@/lib/types";
import { Avatar } from "./Avatar";

interface Props {
  onClose: () => void;
  onCreated: (conv: Conversation) => void;
}

export function NewGroupModal({ onClose, onCreated }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.getContacts().then(setContacts).catch(() => {}); }, []);

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (selected.length === 0) {
      setError("Pick at least one member.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const conv = await api.createGroup(name.trim(), selected, description.trim() || undefined);
      onCreated(conv);
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
          <h2>New group</h2>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={create}>
          <div className="field">
            <label>Group name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Description (optional)</label>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="field">
            <label>Members ({selected.length} selected)</label>
            <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
              {contacts.length === 0 ? (
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Add contacts first to invite them.
                </div>
              ) : (
                contacts.map((c) => {
                  const sel = selected.includes(c.contact_user.id);
                  return (
                    <div key={c.id}
                      className={`selectable ${sel ? "sel" : ""}`}
                      onClick={() => toggle(c.contact_user.id)}>
                      <div className="who">
                        <Avatar name={c.nickname || c.contact_user.full_name}
                          id={c.contact_user.id} url={c.contact_user.avatar_url} size={32} />
                        <span style={{ fontSize: 14 }}>{c.nickname || c.contact_user.full_name}</span>
                      </div>
                      {sel && <Check size={16} color="var(--signal-blue)" />}
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <button className="btn" disabled={busy}>{busy ? "Creating…" : "Create group"}</button>
        </form>
      </div>
    </div>
  );
}
