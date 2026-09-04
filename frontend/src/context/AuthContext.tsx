import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { authService } from "../services/auth";
import type { User } from "../types/auth";
type Value = {
  user: User | null;
  loading: boolean;
  login: (e: string, p: string) => Promise<void>;
  register: (n: string, e: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
};
const Context = createContext<Value | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    authService
      .me()
      .then((r) => setUser(r.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  return (
    <Context.Provider
      value={{
        user,
        loading,
        login: async (e, p) => setUser((await authService.login(e, p)).user),
        register: async (n, e, p) =>
          setUser((await authService.register(n, e, p)).user),
        logout: async () => {
          await authService.logout();
          setUser(null);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
// Auth hook intentionally lives with its provider to keep the public API cohesive.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const v = useContext(Context);
  if (!v) throw Error("AuthProvider missing");
  return v;
}
