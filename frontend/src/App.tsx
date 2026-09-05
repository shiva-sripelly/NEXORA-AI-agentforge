import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { AuthPage } from "./pages/AuthPage";
import { ComingSoon } from "./pages/ComingSoon";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { ChatWorkspace } from "./pages/ChatWorkspace";
import { DocumentsPage } from "./pages/DocumentsPage";
import { MCPPage } from "./pages/MCPPage";
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/app" element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="chat" element={<ChatWorkspace />} />
              <Route path="chat/:id" element={<ChatWorkspace />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="knowledge" element={<DocumentsPage />} />
              <Route path="tools" element={<MCPPage />} />
              <Route path="mcp" element={<MCPPage />} />
              <Route path="*" element={<ComingSoon />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
