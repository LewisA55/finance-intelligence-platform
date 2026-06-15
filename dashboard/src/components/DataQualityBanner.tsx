interface DataQualityBannerProps {
  hasIssue: boolean;
  domainsAffected: number;
  monthLabel: string;
}

/**
 * First-class trust signal — answers "what can I trust?" before any number is read.
 * The warehouse intentionally retains control exceptions rather than hiding them,
 * so they surface here at the top of the command center (amber), and a clean close
 * is affirmed explicitly (green).
 */
export function DataQualityBanner({
  hasIssue,
  domainsAffected,
  monthLabel,
}: DataQualityBannerProps) {
  return (
    <div className={`trustbar ${hasIssue ? 'warn' : 'ok'}`}>
      <div className="tb-icon">{hasIssue ? '⚠' : '✓'}</div>
      <div className="tb-body">
        <div className="tb-head">Control status · {monthLabel}</div>
        <div className="tb-text">
          {hasIssue ? (
            <>
              <strong>Trust with review.</strong> Control exceptions are flagged in{' '}
              {domainsAffected} domain{domainsAffected === 1 ? '' : 's'}. Figures remain on a
              governed Company-Total basis; see the Control Tower before sign-off.
            </>
          ) : (
            <>
              <strong>Trusted.</strong> All cross-domain controls are clean this month and
              every figure is dbt-validated on a scope-safe Company-Total basis.
            </>
          )}
        </div>
      </div>
    </div>
  );
}
