import { useCallback, useEffect, useRef, useState } from "react";
/**
 * Minimal async-data hook with manual refetch and cache-friendly dependency
 * tracking. We bake our own instead of pulling SWR so the bundle stays tiny
 * and the SSE invalidation flow stays explicit.
 */
export function useAsync(fetcher, deps) {
    const [state, setState] = useState({
        data: undefined,
        loading: true,
        error: null,
    });
    const latestRunId = useRef(0);
    const refetch = useCallback(() => {
        const runId = ++latestRunId.current;
        setState((prev) => ({ ...prev, loading: true, error: null }));
        fetcher()
            .then((data) => {
            if (runId !== latestRunId.current)
                return;
            setState({ data, loading: false, error: null });
        })
            .catch((err) => {
            if (runId !== latestRunId.current)
                return;
            setState({
                data: undefined,
                loading: false,
                error: err instanceof Error ? err : new Error(String(err)),
            });
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
    useEffect(() => {
        refetch();
    }, [refetch]);
    return { ...state, refetch };
}
