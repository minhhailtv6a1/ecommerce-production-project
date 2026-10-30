"use client";

import { createContext, useContext, useMemo, useState } from "react";
import { getMe, login, register } from "@/lib/api/auth.api";
import type { AuthCredentials, AuthUser } from "@/types/auth";

interface AuthSession {
  token: string;
  user: AuthUser;
  expiresIn: number;
}

interface AuthContextValue {
  session: AuthSession | null;
  signIn: (credentials: AuthCredentials) => Promise<AuthUser>;
  signUp: (credentials: AuthCredentials) => Promise<AuthUser>;
  verifySession: () => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      async signIn(credentials) {
        const response = await login(credentials);
        setSession({
          token: response.access_token,
          user: response.user,
          expiresIn: response.expires_in,
        });
        return response.user;
      },
      async signUp(credentials) {
        const response = await register(credentials);
        setSession({
          token: response.access_token,
          user: response.user,
          expiresIn: response.expires_in,
        });
        return response.user;
      },
      async verifySession() {
        if (!session) throw new Error("Chưa có phiên đăng nhập trong bộ nhớ.");
        const user = await getMe(session.token);
        setSession((current) => (current ? { ...current, user } : null));
        return user;
      },
      logout() {
        setSession(null);
      },
    }),
    [session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth phải được dùng bên trong AuthProvider.");
  return context;
}
