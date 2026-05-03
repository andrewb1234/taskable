import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
export function ResizableSplit({ direction, size, onSizeChange, defaultSize = 288, minSize = 160, maxSize = 800, storageKey, first, second, className, }) {
    const containerRef = useRef(null);
    const [internalSize, setInternalSize] = useState(() => {
        if (size !== undefined)
            return size;
        if (storageKey) {
            const raw = localStorage.getItem(storageKey);
            const parsed = raw ? Number(raw) : NaN;
            if (Number.isFinite(parsed) && parsed >= minSize && parsed <= maxSize) {
                return parsed;
            }
        }
        return defaultSize;
    });
    const currentSize = size ?? internalSize;
    const [dragging, setDragging] = useState(false);
    const setSize = useCallback((next) => {
        const clamped = Math.max(minSize, Math.min(maxSize, next));
        if (size === undefined)
            setInternalSize(clamped);
        onSizeChange?.(clamped);
        if (storageKey)
            localStorage.setItem(storageKey, String(clamped));
    }, [minSize, maxSize, onSizeChange, size, storageKey]);
    const onPointerDown = useCallback((e) => {
        e.preventDefault();
        setDragging(true);
        e.target.setPointerCapture(e.pointerId);
    }, []);
    const onPointerMove = useCallback((e) => {
        if (!dragging)
            return;
        const el = containerRef.current;
        if (!el)
            return;
        const rect = el.getBoundingClientRect();
        const next = direction === "horizontal"
            ? e.clientX - rect.left
            : e.clientY - rect.top;
        setSize(next);
    }, [dragging, direction, setSize]);
    const onPointerUp = useCallback((e) => {
        setDragging(false);
        try {
            e.target.releasePointerCapture(e.pointerId);
        }
        catch {
            /* not captured */
        }
    }, []);
    // Restore a global body cursor while dragging so the feedback is clear
    // even when the pointer leaves the gutter briefly.
    useEffect(() => {
        if (!dragging)
            return;
        const prev = document.body.style.cursor;
        document.body.style.cursor =
            direction === "horizontal" ? "col-resize" : "row-resize";
        document.body.style.userSelect = "none";
        return () => {
            document.body.style.cursor = prev;
            document.body.style.userSelect = "";
        };
    }, [dragging, direction]);
    const firstStyle = useMemo(() => direction === "horizontal"
        ? { width: currentSize, flex: "0 0 auto" }
        : { height: currentSize, flex: "0 0 auto" }, [direction, currentSize]);
    return (_jsxs("div", { ref: containerRef, className: cn("flex h-full w-full min-h-0", direction === "horizontal" ? "flex-row" : "flex-col", className), children: [_jsx("div", { style: firstStyle, className: "flex min-h-0 min-w-0 overflow-hidden", children: first }), _jsx("div", { role: "separator", "aria-orientation": direction === "horizontal" ? "vertical" : "horizontal", "aria-label": "Resize pane", onPointerDown: onPointerDown, onPointerMove: onPointerMove, onPointerUp: onPointerUp, className: cn("group relative shrink-0 bg-border/30 transition-colors hover:bg-primary/50", direction === "horizontal"
                    ? "w-1 cursor-col-resize"
                    : "h-1 cursor-row-resize", dragging && "bg-primary"), children: _jsx("div", { className: cn("absolute", direction === "horizontal"
                        ? "inset-y-0 -left-1 -right-1"
                        : "inset-x-0 -top-1 -bottom-1") }) }), _jsx("div", { className: "flex min-h-0 min-w-0 flex-1 overflow-hidden", children: second })] }));
}
