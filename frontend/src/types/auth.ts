export type User = {
  id: string;
  name: string;
  email: string;
  role: "USER" | "ADMIN";
  is_active: boolean;
  created_at: string;
};
export type AuthResponse = { success: boolean; user: User };
