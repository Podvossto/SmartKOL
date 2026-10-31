/** `field` names the form input a validation error belongs to (null = a general error). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly field: string | null = null,
  ) {
    super(message);
  }
}

/** What went wrong in words, for a reply that carries no message of its own (a proxy page, a validation list, a bare status). */
function describe(status: number, detail: unknown): string {
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    const where = Array.isArray(detail[0].loc) ? detail[0].loc.filter((p: unknown) => p !== "body" && p !== "query").join(".") : "";
    return `The request was not accepted${where ? ` (${where}: ${detail[0].msg})` : `: ${detail[0].msg}`}.`;
  }
  if (status === 404) return "Not found. It may have been deleted.";
  if (status === 401 || status === 403) return "Not allowed. Check the key in Settings.";
  if (status === 502 || status === 503 || status === 504) return `The backend did not answer (HTTP ${status}). It may be starting or stopped; wait a moment and try again.`;
  if (status >= 500) return `The backend hit an error (HTTP ${status}). The details are in its log; try again.`;
  return `The request failed (HTTP ${status}).`;
}

export async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach the backend. Check that it is running (docker compose up) and that you are online.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    if (typeof detail === "string") throw new ApiError(detail);
    if (detail && typeof detail.message === "string") throw new ApiError(detail.message, detail.field ?? null);
    throw new ApiError(describe(res.status, detail));
  }
  return data as T;
}
