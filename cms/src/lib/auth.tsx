// Minimal auth: the editor picks a role, which selects a demo bearer token.
// In production this is replaced by a real login (OIDC) — see README.
import { createContext, useContext, useState, ReactNode } from "react";
import type { Role } from "./types";

// Demo tokens must match the backend's EDITOR_TOKEN / ADMIN_TOKEN.
const TOKENS: Record<Role, string> = {
  editor: import.meta.env.VITE_EDITOR_TOKEN || "editor-token",
  admin: import.meta.env.VITE_ADMIN_TOKEN || "admin-token",
};

interface AuthState {
  role: Role;
  token: string;
  setRole: (r: Role) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(
    (localStorage.getItem("peblo_role") as Role) || "admin"
  );
  const setRole = (r: Role) => {
    localStorage.setItem("peblo_role", r);
    setRoleState(r);
  };
  return (
    <AuthContext.Provider value={{ role, token: TOKENS[role], setRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
