import { FileText, Plus, Trash2, UploadCloud } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { safeError } from "../api/client";
import { documents } from "../services/documents";
import type { Document } from "../types/document";
export function DocumentsPage() {
  const navigate = useNavigate(),
    [items, setItems] = useState<Document[]>([]),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    input = useRef<HTMLInputElement>(null),
    uploadLock = useRef(false),
    [deleting, setDeleting] = useState<string[]>([]);
  async function load() {
    try {
      setItems(await documents.all());
    } catch (e) {
      setError(safeError(e, "Unable to load documents. Check your connection and try again."));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    // Initial remote synchronization is intentionally effect-driven.
    // oxlint-disable-next-line react/set-state-in-effect
    load();
  }, []);
  async function upload(file?: File) {
    if (!file || uploadLock.current) return;
    if (!/\.(pdf|txt|md)$/i.test(file.name)) {
      setError("Supported file types are PDF, TXT, and Markdown.");
      if (input.current) input.current.value = "";
      return;
    }
    uploadLock.current = true;
    setBusy(true);
    setError("");
    try {
      const doc = await documents.upload(file);
      setItems((v) => [doc, ...v.filter((x) => x.id !== doc.id)]);
    } catch (e) {
      setError(safeError(e, "Document upload failed. Check your connection and try again."));
      try {
        setItems(await documents.all());
      } catch {
        // Keep the original upload error when the follow-up refresh also fails.
      }
    } finally {
      uploadLock.current = false;
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function remove(doc: Document) {
    if (!confirm(`Delete "${doc.display_name}"? This cannot be undone.`))
      return;
    setError("");
    setDeleting((v) => [...v, doc.id]);
    try {
      await documents.remove(doc.id);
      setItems((v) => v.filter((x) => x.id !== doc.id));
    } catch (e) {
      setError(
        safeError(e, "Unable to delete this document. Check your connection and try again."),
      );
    } finally {
      setDeleting((v) => v.filter((id) => id !== doc.id));
    }
  }
  return (
    <div className="documents-page">
      <header>
        <div>
          <small>KNOWLEDGE WORKSPACE</small>
          <h1>Knowledge Base</h1>
          <p>
            Upload documents to give AgentForge additional knowledge for
            RAG-powered conversations.
          </p>
        </div>
        <button onClick={() => input.current?.click()} disabled={busy}>
          <Plus />
          {busy ? "Processing..." : "Upload Document"}
        </button>
        <input
          ref={input}
          hidden
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          onChange={(e) => upload(e.target.files?.[0])}
        />
      </header>
      <section
        className="drop-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          upload(e.dataTransfer.files[0]);
        }}
        onClick={() => !busy && input.current?.click()}
      >
        <UploadCloud />
        <strong>
          {busy
            ? "Uploading and processing..."
            : "Drop PDF, TXT or Markdown files here"}
        </strong>
        <span>or click to browse - Server upload size limit applies</span>
      </section>
      {error && <p className="document-error">{error}</p>}
      <section className="document-table">
        <div className="table-head">
          Your documents <span>{items.length} files</span>
          <button disabled={busy} onClick={() => { setError(""); void load(); }}>Refresh</button>
        </div>
        {loading ? (
          <div className="documents-empty">Loading documents...</div>
        ) : items.length === 0 ? (
          <div className="documents-empty">
            <FileText />
            <strong>No documents yet</strong>
            <span>Upload your first source to enable grounded answers.</span>
          </div>
        ) : (
          items.map((doc) => (
            <article key={doc.id}>
              <FileText />
              <div>
                <strong>{doc.display_name}</strong>
                <small>
                  {doc.content_type.includes("pdf")
                    ? "PDF"
                    : doc.display_name.toLowerCase().endsWith(".md")
                      ? "Markdown"
                      : "TXT"}{" "}
                  -{" "}
                  {doc.file_size < 1024
                    ? `${doc.file_size} B`
                    : `${(doc.file_size / 1024).toFixed(1)} KB`}{" "}
                  - {doc.chunk_count}{" "}
                  {doc.chunk_count === 1 ? "chunk" : "chunks"} -{" "}
                  {new Date(doc.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </small>
                {doc.status === "failed" && (
                  <em>Document processing failed. Try uploading again.</em>
                )}
              </div>
              <span className={`doc-status ${doc.status}`}>{doc.status}</span>
              {doc.status === "ready" && (
                <button
                  className="use-chat"
                  onClick={() =>
                    navigate("/app/chat", { state: { documentId: doc.id } })
                  }
                >
                  Use in Chat
                </button>
              )}
              <button title="Delete" aria-label={`Delete ${doc.display_name}`} disabled={deleting.includes(doc.id) || doc.status === "processing" || doc.status === "uploaded"} onClick={() => remove(doc)}>
                <Trash2 />
              </button>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
