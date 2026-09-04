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
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (response.status === 401 && retry && path != "/auth/refresh") {
    const refresh = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refresh.ok) return api<T>(path, options, false);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      body.detail || body.error?.message || "Something went wrong",
      response.status,
    );
  return body;
}
