"use client";

// Client-side provider stack. Kept separate from layout.tsx so the layout can
// remain a Server Component while these (which need browser APIs) are Client
// Components.

import { AuthProvider } from "@/context/AuthContext";
import { SocketProvider } from "@/context/SocketContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <SocketProvider>{children}</SocketProvider>
    </AuthProvider>
  );
}
