import { useEffect, useState } from 'react';

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

/**
 * Runs an async query function once on mount (and whenever `deps` change).
 * Generic over the query so views just pass a typed loader from queries.ts.
 */
export function useQuery<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
): QueryState<T> {
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    loader()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: error instanceof Error ? error : new Error(String(error)),
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
