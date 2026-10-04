/** Display helpers for simulation metrics (no engineering math). */

export function formatNum(
  value: number | null | undefined,
  digits = 4,
): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (!Number.isFinite(value)) {
    return '—'
  }
  if (Math.abs(value) >= 1000 || Math.abs(value) < 0.001) {
    return value.toExponential(3)
  }
  return value.toPrecision(digits)
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  return `${(value * 100).toFixed(2)} %`
}

export function shortHash(value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  return value.length > 12 ? `${value.slice(0, 12)}…` : value
}
