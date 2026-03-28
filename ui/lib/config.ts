const rawApiBase = process.env.NEXT_PUBLIC_API_BASE;

function normalizeApiBase(value: string | undefined): string {
  if (!value) {
    return "";
  }

  const trimmed = value.trim();
  if (!trimmed || trimmed === "undefined" || trimmed === "null") {
    return "";
  }

  return trimmed.replace(/\/+$/, "");
}

export const API_BASE = normalizeApiBase(rawApiBase);
