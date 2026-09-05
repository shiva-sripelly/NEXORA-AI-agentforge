const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const isForm = options.body instanceof FormData;
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: isForm
      ? options.headers
      : { "Content-Type": "application/json", ...options.headers },
  });
  if (response.status === 401 && retry && path != "/auth/refresh") {
    const refresh = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refresh.ok) return api<T>(path, options, false);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail?.message === "string"
          ? detail.message
          : typeof body.error?.message === "string"
            ? body.error.message
            : "Something went wrong";
    throw new ApiError(message, response.status);
  }
  return body;
}

// Do not display arbitrary server or network exception text in document/chat UI.
export function safeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session expired. Please log in again.";
    if (error.status === 403) return "You do not have access to this resource.";
    if (error.status === 404) return "This item is unavailable or has been deleted. Refresh and try again.";
    if (error.status === 413) return "The document exceeds the server upload size limit.";
    if (error.status === 415) return "Upload a valid PDF, TXT, or Markdown file.";
    if (error.status === 422) return "The request could not be processed. Check your input; document processing or embeddings may be unavailable.";
  }
  return fallback;
}
