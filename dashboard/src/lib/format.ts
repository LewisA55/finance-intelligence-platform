const GBP = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  maximumFractionDigits: 0,
});

/** Compact GBP, e.g. £67.4M, £5.8M, £205K. */
export function formatGbpCompact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `£${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `£${(value / 1_000).toFixed(0)}K`;
  return GBP.format(value);
}

/** Full GBP with thousands separators, no decimals. */
export function formatGbp(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return GBP.format(value);
}

/** Ratio (0.975) -> "97.5%". */
export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

/** Integer with thousands separators. */
export function formatCount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('en-GB').format(value);
}

/** Signed percentage-point or percentage delta for MoM movement chips. */
export function formatSignedPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}
