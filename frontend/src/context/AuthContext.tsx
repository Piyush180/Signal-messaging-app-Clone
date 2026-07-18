"use client";

// Auth state for the whole app: who is logged in, plus login/logout helpers.
// The token lives in localStorage (see DESIGN.md for the tradeoff vs. an
// httpOnly cookie). On mount we try to restore the session by calling /me.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api } from "@/lib/api";
import { TOKEN_KEY } from "@/lib/config";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (phone: string, code: string, fullName?: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      const token =
        typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch {
        // Note: we do NOT log the user out on a slow/failed network here beyond
        // a genuine 401. api.ts only clears the token on a real 401 response, so
        // a momentarily-down backend won't nuke a valid session.
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    restore();

    const onUnauthorized = () => setUser(null);
    window.addEventListener("signal:unauthorized", onUnauthorized);
    return () => {
      cancelled = true;
      window.removeEventListener("signal:unauthorized", onUnauthorized);
    };
  }, []);

  const login = useCallback(async (phone: string, code: string, fullName?: string) => {
    const res = await api.verifyOtp(phone, code, fullName);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore network errors on logout */
    }
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
