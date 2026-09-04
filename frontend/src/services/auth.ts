import { api } from "../api/client";
import type { AuthResponse } from "../types/auth";
export const authService = {
  me: () => api<AuthResponse>("/auth/me"),
  login: (email: string, password: string) =>
    api<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (name: string, email: string, password: string) =>
    api<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    }),
  logout: () => api<{ message: string }>("/auth/logout", { method: "POST" }),
};
