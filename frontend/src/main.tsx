import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./chat.css";
import "./documents.css";
import "./mcp.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
