"use client";

// Renders a user/group avatar. If there's an image URL we use it; otherwise we
// fall back to a colored circle with the first initial. The color is derived
// deterministically from the name+id so the same person always gets the same one.

import { useState } from "react";

const COLORS = [
  "#3a76f0", "#e0555f", "#2e9e5b", "#8e5bd0", "#e0803a",
  "#0f9e9e", "#d0468f", "#5b6ed0", "#c9a227", "#4a90d9",
];

function pickColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

interface Props {
  name?: string | null;
  id?: number | string;
  url?: string | null;
  size?: number;
  showPresence?: boolean;
  online?: boolean;
}

export function Avatar({ name, id, url, size = 42, showPresence, online }: Props) {
  const [broken, setBroken] = useState(false);
  const initial = (name?.trim()?.[0] || "?").toUpperCase();
  const color = pickColor(`${name ?? ""}:${id ?? ""}`);

  const inner =
    url && !broken ? (
      <img
        className="avatar"
        src={url}
        alt={name ?? "avatar"}
        width={size}
        height={size}
        style={{ width: size, height: size }}
        onError={() => setBroken(true)}
      />
    ) : (
      <div
        className="avatar"
        style={{ width: size, height: size, background: color, fontSize: size * 0.42 }}
      >
        {initial}
      </div>
    );

  if (!showPresence) return inner;
  return (
    <div className="avatar-wrap">
      {inner}
      <span className={`presence ${online ? "on" : "off"}`} />
    </div>
  );
}
