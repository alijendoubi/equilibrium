const MAX_PARAM_LENGTH = 200;

/** First value of a search param, capped in length. Never throws. */
export function firstParam(value: string | string[] | undefined): string {
  const first = Array.isArray(value) ? value[0] : value;
  return (first ?? "").slice(0, MAX_PARAM_LENGTH);
}

/** Decodes a dynamic route segment such as "MONDO%3A0009267". Returns null if it is malformed. */
export function decodeSegment(segment: string): string | null {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}
