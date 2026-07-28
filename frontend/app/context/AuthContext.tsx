"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

export type User = {
  full_name: string;
  email: string;
  role: "owner" | "member";
};

interface AuthContextType {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  authFetch: <T>(path: string, init?: RequestInit) => Promise<T>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore authentication state from localStorage on initial client mount
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem("leadgen_token");
      const savedUser = localStorage.getItem("leadgen_user");
      if (savedToken && savedUser) {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      }
    } catch (error) {
      console.error("Failed to restore authentication state:", error);
      localStorage.removeItem("leadgen_token");
      localStorage.removeItem("leadgen_user");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback((newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem("leadgen_token", newToken);
    localStorage.setItem("leadgen_user", JSON.stringify(newUser));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("leadgen_token");
    localStorage.removeItem("leadgen_user");
  }, []);

  const authFetch = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      // Prefer state token, fallback to localStorage if state is in transition
      const activeToken = token || (typeof window !== "undefined" ? localStorage.getItem("leadgen_token") : null);

      const reqHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        ...(activeToken ? { Authorization: `Bearer ${activeToken}` } : {}),
        ...((init?.headers as Record<string, string>) || {}),
      };

      const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: reqHeaders,
      });

      if (response.status === 401) {
        // Clear invalid or expired credentials and redirect to login state
        logout();
        throw new Error("Session expired or unauthorized. Please log in.");
      }

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status} ${response.statusText}`);
      }

      return response.json() as Promise<T>;
    },
    [token, logout]
  );

  return (
    <AuthContext.Provider value={{ token, user, isLoading, login, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
