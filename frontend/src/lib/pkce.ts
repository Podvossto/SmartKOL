const VERIFIER_KEY = "smartkol.openrouter.verifier";
const STATE_KEY = "smartkol.openrouter.state";

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(byteLength: number): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

/** Start OpenRouter OAuth (PKCE, S256): remember verifier + state, then leave for openrouter.ai. */
export async function startOpenRouterLogin(): Promise<void> {
  const verifier = randomString(48);
  const state = randomString(16);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);

  const url = new URL("https://openrouter.ai/auth");
  url.searchParams.set("callback_url", `${window.location.origin}/settings/openrouter/callback`);
  url.searchParams.set("code_challenge", base64Url(new Uint8Array(digest)));
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("state", state);
  window.location.assign(url.toString());
}

/** Read and clear the stored verifier; returns null when the callback has no matching login attempt. */
export function takeOpenRouterLogin(returnedState: string | null): string | null {
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  const state = sessionStorage.getItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  sessionStorage.removeItem(STATE_KEY);
  if (!verifier || !state || state !== returnedState) return null;
  return verifier;
}
