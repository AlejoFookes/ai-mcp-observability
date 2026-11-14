const TOKEN_KEY = "multimcp_ingest_token";

export function getIngestToken(): string | null {
  const value = sessionStorage.getItem(TOKEN_KEY);
  if (value === null || value.trim() === "") {
    return null;
  }
  return value;
}

export function setIngestToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearIngestToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}
