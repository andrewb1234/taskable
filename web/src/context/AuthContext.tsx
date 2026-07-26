import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  createLocalSession,
  getAuthProviders,
  getMe,
  logout,
  getLoginUrl,
  type AuthProviders,
  type AuthUser,
} from "@/lib/api";
import { clearAsyncCache } from "@/hooks/useAsync";

interface AuthState {
  user: AuthUser | null;
  providers: AuthProviders;
  loading: boolean;
  login: () => void;
  loginWithLocalApiKey: (apiKey: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [providers, setProviders] = useState<AuthProviders>({
    google: false,
    local_api_key: false,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getMe().catch(() => null),
      getAuthProviders().catch(() => ({
        google: false,
        local_api_key: false,
      })),
    ])
      .then(([currentUser, configuredProviders]) => {
        setUser(currentUser);
        setProviders(configuredProviders);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(() => {
    window.location.href = getLoginUrl();
  }, []);

  const loginWithLocalApiKey = useCallback(async (apiKey: string) => {
    await createLocalSession(apiKey);
    clearAsyncCache();
    setUser(await getMe());
  }, []);

  const doLogout = useCallback(async () => {
    try {
      await logout();
    } catch {
      /* ignore */
    }
    clearAsyncCache();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        providers,
        loading,
        login,
        loginWithLocalApiKey,
        logout: doLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
