import { TopBar } from './TopBar';

interface PlaceholderPageProps {
  title: string;
  subtitle: string;
  purpose: string;
  questions: string[];
  sources: string[];
}

/** Polished "planned" shell stating intended purpose and data sources. */
export function PlaceholderPage({ title, subtitle, purpose, questions, sources }: PlaceholderPageProps) {
  return (
    <>
      <TopBar
        title={title}
        subtitle={subtitle}
        actions={<span className="scope-pill planned">Planned</span>}
      />
      <div className="placeholder-page">
        <div className="panel">
          <h3>Purpose</h3>
          <p className="placeholder-purpose">{purpose}</p>
          <h4>Questions this page will answer</h4>
          <ul>
            {questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h3>Planned data sources</h3>
          <ul className="source-list">
            {sources.map((s) => (
              <li key={s}><code>{s}</code></li>
            ))}
          </ul>
          <p className="placeholder-note">
            These governed Gold marts already exist in the warehouse and are exported to
            Parquet; this page will query them through the same DuckDB-WASM layer.
          </p>
        </div>
      </div>
    </>
  );
}
