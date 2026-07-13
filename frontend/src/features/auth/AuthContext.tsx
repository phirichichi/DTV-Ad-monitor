import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  fetchCurrentUser,
  login as loginRequest,
  refreshAccessToken,
} from "../../api/auth";
import { CurrentUser } from "../../types/auth";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const accessToken = localStorage.getItem("dtv_access_token");
      const refreshToken = localStorage.getItem("dtv_refresh_token");

      if (!accessToken) {
        setLoading(false);
        return;
      }

      try {
        setUser(await fetchCurrentUser());
      } catch {
        if (!refreshToken) {
          localStorage.removeItem("dtv_access_token");
          setUser(null);
          setLoading(false);
          return;
        }

        try {
          const refreshed = await refreshAccessToken(refreshToken);
          localStorage.setItem("dtv_access_token", refreshed.access_token);
          setUser(await fetchCurrentUser());
        } catch {
          localStorage.removeItem("dtv_access_token");
          localStorage.removeItem("dtv_refresh_token");
          setUser(null);
        }
      } finally {
        setLoading(false);
      }
    };

    init();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login: async (email: string, password: string) => {
        const response = await loginRequest(email, password);

        localStorage.setItem("dtv_access_token", response.access_token);
        localStorage.setItem("dtv_refresh_token", response.refresh_token);

        setUser(await fetchCurrentUser());
      },
      logout: async () => {
        localStorage.removeItem("dtv_access_token");
        localStorage.removeItem("dtv_refresh_token");
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}