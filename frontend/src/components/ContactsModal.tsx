"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact } from "@/lib/types";
import { Avatar } from "./Avatar";

interface Props {
  onClose: () => void;
  onMessage: (contactUserId: number) => void;
}

export function ContactsModal({ onClose, onMessage }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [phone, setPhone] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.getContacts().then(setContacts).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.addContact(phone.trim(), nickname.trim() || undefined);
      setPhone("");
      setNickname("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await api.deleteContact(id);
    setContacts((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Contacts</h2>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={add} style={{ marginBottom: 18 }}>
          <div className="field">
            <label>Add by phone number</label>
            <input className="input" placeholder="+15559876543" value={phone}
              onChange={(e) => setPhone(e.target.value)} required />
          </div>
          <div className="field">
            <label>Nickname (optional)</label>
            <input className="input" value={nickname}
              onChange={(e) => setNickname(e.target.value)} />
          </div>
          <button className="btn" disabled={busy}>{busy ? "Adding…" : "Add contact"}</button>
        </form>

        <div>
          {contacts.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", padding: 16 }}>
              No contacts yet.
            </div>
          ) : (
            contacts.map((c) => (
              <div className="list-row" key={c.id}>
                <div className="who">
                  <Avatar name={c.nickname || c.contact_user.full_name} id={c.contact_user.id}
                    url={c.contact_user.avatar_url} size={38} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>
                      {c.nickname || c.contact_user.full_name}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {c.contact_user.phone_number}
                    </div>
                  </div>
                </div>
                <div className="icon-row">
                  <button className="icon-btn" title="Message"
                    onClick={() => onMessage(c.contact_user.id)}>
                    <MessageSquare size={17} color="var(--signal-blue)" />
                  </button>
                  <button className="icon-btn" title="Delete" onClick={() => remove(c.id)}>
                    <Trash2 size={17} color="var(--danger)" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
