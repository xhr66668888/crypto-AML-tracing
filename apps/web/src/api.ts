const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function classifyError(err: unknown): string {
  if (err instanceof TypeError && err.message.includes("fetch")) {
    return "Unable to connect to the server. Please check that the backend is running and try again.";
  }
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    if (msg.includes("cors") || msg.includes("access-control")) {
      return "Cross-origin request blocked. The server may not accept requests from this browser.";
    }
    if (msg.includes("network") || msg.includes("failed to fetch")) {
      return "Network error. Check your connection and ensure the backend is reachable.";
    }
    if (msg.includes("404")) {
      return "The requested resource was not found. Please verify the endpoint exists.";
    }
    if (msg.includes("500") || msg.includes("internal server error")) {
      return "The server encountered an internal error. Please try again in a moment.";
    }
    if (msg.includes("503") || msg.includes("service unavailable")) {
      return "The service is temporarily unavailable. Please try again shortly.";
    }
    if (msg.includes("429") || msg.includes("too many requests")) {
      return "Too many requests. Please wait a moment before trying again.";
    }
    if (msg.includes("timeout") || msg.includes("timed out")) {
      return "The request timed out. The server may be under heavy load.";
    }
    return err.message;
  }
  return "An unexpected error occurred.";
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
        ...options
      });
      if (!response.ok) {
        let message: string;
        try {
          message = await response.text();
        } catch {
          message = response.statusText;
        }
        throw new Error(message || `HTTP ${response.status}`);
      }
      return (await response.json()) as T;
    } catch (err) {
      lastError = err;
      const isRetryable =
        err instanceof TypeError ||
        (err instanceof Error && /network|fetch|timeout|503|429/i.test(err.message));
      if (isRetryable && attempt < MAX_RETRIES) {
        await delay(RETRY_DELAY_MS * (attempt + 1));
        continue;
      }
      break;
    }
  }
  throw new Error(classifyError(lastError));
}

export function compactAddress(address: string): string {
  if (address.length <= 14) return address;
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}
