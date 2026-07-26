import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Two-pane split with a draggable gutter. The first pane's size is
 * controlled — width for horizontal splits, height for vertical splits —
 * and clamped to sensible min/max bounds. The size is persisted to
 * localStorage under ``storageKey`` so the layout survives reloads.
 *
 * Deliberately dependency-free (no react-resizable / react-split-pane)
 * since the three use-cases we need (sidebar, knowledge tree, kanban header)
 * all fit the same minimal model.
 */
interface ResizableSplitProps {
  direction: "horizontal" | "vertical";
  /** Controlled first-pane size in px. Uncontrolled if omitted. */
  size?: number;
  onSizeChange?: (size: number) => void;
  /** Uncontrolled initial size in px. */
  defaultSize?: number;
  minSize?: number;
  maxSize?: number;
  /** Keep at least this many pixels available for the second pane. */
  minSecondSize?: number;
  /** Persist size under this key in localStorage. */
  storageKey?: string;
  separatorLabel?: string;
  collapseFirstBelowMd?: boolean;
  first: React.ReactNode;
  second: React.ReactNode;
  className?: string;
}

export function ResizableSplit({
  direction,
  size,
  onSizeChange,
  defaultSize = 288,
  minSize = 160,
  maxSize = 800,
  minSecondSize = 160,
  storageKey,
  separatorLabel = "Resize pane",
  collapseFirstBelowMd = false,
  first,
  second,
  className,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [internalSize, setInternalSize] = useState<number>(() => {
    if (size !== undefined) return size;
    if (storageKey) {
      try {
        const raw = localStorage.getItem(storageKey);
        const parsed = raw ? Number(raw) : NaN;
        if (Number.isFinite(parsed) && parsed >= minSize && parsed <= maxSize) {
          return parsed;
        }
      } catch {
        // Storage can be unavailable in hardened/private browsing contexts.
      }
    }
    return defaultSize;
  });
  const currentSize = size ?? internalSize;
  const currentSizeRef = useRef(currentSize);
  const [dragging, setDragging] = useState(false);

  const persistSize = useCallback(
    (next: number) => {
      if (!storageKey) return;
      try {
        localStorage.setItem(storageKey, String(next));
      } catch {
        // Resizing remains functional when persistence is unavailable.
      }
    },
    [storageKey],
  );

  const setSize = useCallback(
    (next: number, persist = true) => {
      const container = containerRef.current;
      const extent = container
        ? direction === "horizontal"
          ? container.getBoundingClientRect().width
          : container.getBoundingClientRect().height
        : 0;
      const availableMax =
        extent > 0
          ? Math.max(minSize, Math.min(maxSize, extent - minSecondSize))
          : maxSize;
      const clamped = Math.max(minSize, Math.min(availableMax, next));
      currentSizeRef.current = clamped;
      if (size === undefined) setInternalSize(clamped);
      onSizeChange?.(clamped);
      if (persist) persistSize(clamped);
    },
    [
      direction,
      minSecondSize,
      minSize,
      maxSize,
      onSizeChange,
      persistSize,
      size,
    ],
  );

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const next =
        direction === "horizontal"
          ? e.clientX - rect.left
          : e.clientY - rect.top;
      setSize(next, false);
    },
    [dragging, direction, setSize],
  );

  const finishPointerResize = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      setDragging(false);
      persistSize(currentSizeRef.current);
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* Pointer capture may already have been released by the browser. */
      }
    },
    [dragging, persistSize],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const decrement =
        direction === "horizontal" ? e.key === "ArrowLeft" : e.key === "ArrowUp";
      const increment =
        direction === "horizontal"
          ? e.key === "ArrowRight"
          : e.key === "ArrowDown";
      if (!decrement && !increment) return;
      e.preventDefault();
      setSize(currentSize + (increment ? 16 : -16));
    },
    [currentSize, direction, setSize],
  );

  // Restore a global body cursor while dragging so the feedback is clear
  // even when the pointer leaves the gutter briefly.
  useEffect(() => {
    currentSizeRef.current = currentSize;
  }, [currentSize]);

  useEffect(() => {
    const clampToContainer = () => setSize(currentSizeRef.current, false);
    clampToContainer();
    window.addEventListener("resize", clampToContainer);
    return () => window.removeEventListener("resize", clampToContainer);
  }, [setSize]);

  useEffect(() => {
    if (!dragging) return;
    const prev = document.body.style.cursor;
    document.body.style.cursor =
      direction === "horizontal" ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none";
    return () => {
      document.body.style.cursor = prev;
      document.body.style.userSelect = "";
    };
  }, [dragging, direction]);

  const firstStyle = useMemo<React.CSSProperties>(
    () =>
      direction === "horizontal"
        ? { width: currentSize, flex: "0 0 auto" }
        : { height: currentSize, flex: "0 0 auto" },
    [direction, currentSize],
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "flex h-full w-full min-h-0 min-w-0 overflow-hidden",
        direction === "horizontal" ? "flex-row" : "flex-col",
        className,
      )}
    >
      <div
        style={firstStyle}
        className={cn(
          "flex min-h-0 min-w-0 overflow-hidden",
          collapseFirstBelowMd && "max-md:hidden",
        )}
      >
        {first}
      </div>
      <div
        role="separator"
        aria-orientation={direction === "horizontal" ? "vertical" : "horizontal"}
        aria-label={separatorLabel}
        aria-valuemin={minSize}
        aria-valuemax={maxSize}
        aria-valuenow={Math.round(currentSize)}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={finishPointerResize}
        onPointerCancel={finishPointerResize}
        onLostPointerCapture={finishPointerResize}
        onKeyDown={onKeyDown}
        className={cn(
          "focus-ring group relative shrink-0 bg-border/30 transition-colors hover:bg-primary/50 focus-visible:bg-primary",
          direction === "horizontal"
            ? "w-1 cursor-col-resize"
            : "h-1 cursor-row-resize",
          collapseFirstBelowMd && "max-md:hidden",
          dragging && "bg-primary",
        )}
      >
        {/* Fat hit-area centered on the thin visual line. */}
        <div
          className={cn(
            "absolute",
            direction === "horizontal"
              ? "inset-y-0 -left-1 -right-1"
              : "inset-x-0 -top-1 -bottom-1",
          )}
        />
      </div>
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        {second}
      </div>
    </div>
  );
}
