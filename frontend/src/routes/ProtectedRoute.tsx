import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
export function ProtectedRoute() {
  const { user, loading } = useAuth();
  return loading ? (
    <div className="loader">Forging your workspace…</div>
  ) : user ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace />
  );
}
