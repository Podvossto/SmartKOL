/** `field` names the form input a validation error belongs to (null = a general error). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly field: string | null = null,
  ) {
    super(message);
  }
}

export async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    if (typeof detail === "string") throw new ApiError(detail);
    if (detail && typeof detail.message === "string") throw new ApiError(detail.message, detail.field ?? null);
    throw new ApiError("Request failed");
  }
  return data as T;
}
