import type { AccountVariance } from '../types';

/**
 * Presentation-basis guardrails.
 *
 * The warehouse deliberately retains as-found audit telemetry (synthetic
 * defects included) so the control layer has something to catch. These rules
 * decide what is safe to PRESENT in CFO-facing views, the same way management
 * accounts sit on an adjusted basis above the raw ledger. Excluded items are
 * disclosed, never hidden.
 */

export const SOURCE_COMPLETENESS = {
  /** Budgets below this are too small to distinguish underspend from noise. */
  budgetFloorGbp: 100_000,
  /** Actuals below this share of budget read as missing capture, not thrift. */
  captureRatio: 0.2,
};

/**
 * Expense lines whose "favourable" variance is more plausibly missing source
 * capture than genuine underspend: a material budget with almost no actuals.
 * These belong in the governance lane, not a variance leaderboard.
 */
export function isSuspectedIncompleteCapture(row: AccountVariance): boolean {
  return (
    row.account_class === 'Expense' &&
    row.favourability === 'Favourable' &&
    row.budget >= SOURCE_COMPLETENESS.budgetFloorGbp &&
    row.actual < SOURCE_COMPLETENESS.captureRatio * row.budget
  );
}

/**
 * Materiality: a variance is only presentation-worthy when it exceeds the
 * greater of an absolute floor and a share of the measure it varies against.
 */
export function exceedsMateriality(
  variance: number,
  base: number,
  floorGbp = 50_000,
  share = 0.005,
): boolean {
  return Math.abs(variance) > Math.max(floorGbp, share * Math.abs(base));
}

/**
 * Clip trailing partial periods: drop end-of-series rows that collapse versus
 * the prior period — boundary/partial-month artifacts that would otherwise
 * render as a cliff and read as a business event.
 */
export function clipTrailingPartial<T>(
  rows: T[],
  value: (row: T) => number,
  ratio = 0.7,
  maxDrop = 2,
): T[] {
  const out = [...rows];
  let drops = 0;
  while (
    drops < maxDrop &&
    out.length >= 2 &&
    value(out[out.length - 1]) < ratio * value(out[out.length - 2])
  ) {
    out.pop();
    drops += 1;
  }
  return out;
}
