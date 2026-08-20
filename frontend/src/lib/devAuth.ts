export const DEV_TOKEN_KEY = "mandarinflow:dev-token";
export const DEV_TOKEN_EVENT = "dev-token-updated";

export function readDevToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(DEV_TOKEN_KEY);
}

export function writeDevToken(token: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(DEV_TOKEN_KEY, token);
  window.dispatchEvent(new Event(DEV_TOKEN_EVENT));
}

export function clearDevToken(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(DEV_TOKEN_KEY);
  window.dispatchEvent(new Event(DEV_TOKEN_EVENT));
}
