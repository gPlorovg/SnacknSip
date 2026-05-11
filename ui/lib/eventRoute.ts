/** Сегмент [event_code] из URL (строка или массив). */
export function routeEventCode(
  raw: string | string[] | undefined,
): string {
  if (!raw) return "";
  const v = Array.isArray(raw) ? raw[0] : raw;
  return (v ?? "").trim();
}

/** Код мероприятия из ответа логина, пока Next ещё не отдал params. */
export function storedEventCode(): string {
  if (typeof localStorage === "undefined") return "";
  const raw = localStorage.getItem("event");
  if (!raw) return "";
  try {
    return ((JSON.parse(raw) as { code?: string }).code ?? "").trim();
  } catch {
    return "";
  }
}

export function resolvedEventCode(
  param: string | string[] | undefined,
): string {
  return routeEventCode(param) || storedEventCode();
}
