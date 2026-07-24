export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = "http_error",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    let message = `Yêu cầu thất bại (HTTP ${response.status}).`;
    let code = "http_error";
    try {
      const body = await response.json() as { error?: { code?: string; message?: string } };
      message = body.error?.message || message;
      code = body.error?.code || code;
    } catch {
      // Response không có JSON lỗi; dùng thông báo HTTP phía trên.
    }
    throw new ApiError(message, response.status, code);
  }
  return response.json() as Promise<T>;
}

export function jsonRequest(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}
