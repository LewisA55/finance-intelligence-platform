/**
 * Presentation-basis guardrails (client-side residue).
 *
 * The source of truth for presentation policy is the warehouse: the
 * `presentation_policy` seed and the `mart_cfo_presented_*` marts (see
 * docs/13_presentation_basis.md). Financial Performance consumes the mart
 * flags directly; the source-completeness rule that used to live here now
 * exists only in the warehouse. What remains are the rules for surfaces the
 * marts do not yet cover: trailing clips on curated CSV slices and
 * materiality checks on measures served by the executive mart. Keep the
 * constants aligned with the seed; retire each helper as its surface moves
 * to a presented mart.
 */

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
