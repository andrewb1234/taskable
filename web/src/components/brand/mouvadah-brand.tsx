import type { HTMLAttributes, SVGProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const lockupVariants = cva("inline-flex items-center", {
  variants: {
    size: {
      sm: "gap-2 text-sm",
      md: "gap-2.5 text-base",
      lg: "gap-3 text-xl",
    },
  },
  defaultVariants: {
    size: "md",
  },
});

const markSize = {
  sm: "h-5 w-5",
  md: "h-6 w-6",
  lg: "h-8 w-8",
} as const;

export interface MouvadahMarkProps extends SVGProps<SVGSVGElement> {
  label?: string;
}

/**
 * A deterministic, currentColor brand mark that remains legible at 20px.
 *
 * The central disc and symmetric strokes reference the geometry of an
 * Assyrian winged disc without reproducing a historical artifact. The
 * right-facing center expresses action and forward motion.
 */
export function MouvadahMark({
  className,
  label,
  ...props
}: MouvadahMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0", className)}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
      {...props}
    >
      {label ? <title>{label}</title> : null}
      <circle cx="16" cy="16" r="4.5" stroke="currentColor" strokeWidth="1.75" />
      <path d="m14.25 13.5 4.5 2.5-4.5 2.5v-5Z" fill="currentColor" />
      <path
        d="M11.25 11.7C8.05 11.45 5.3 12.9 3 16c2.3 3.1 5.05 4.55 8.25 4.3"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M20.75 11.7c3.2-.25 5.95 1.2 8.25 4.3-2.3 3.1-5.05 4.55-8.25 4.3"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M16 4.25v4M16 23.75v4M6.65 8.2l2.85 2.85M22.5 20.95l2.85 2.85M25.35 8.2l-2.85 2.85M9.5 20.95 6.65 23.8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export interface MouvadahWordmarkProps
  extends HTMLAttributes<HTMLSpanElement> {
  uppercase?: boolean;
}

export function MouvadahWordmark({
  className,
  uppercase = false,
  ...props
}: MouvadahWordmarkProps) {
  return (
    <span
      className={cn(
        "font-semibold leading-none tracking-[-0.035em]",
        uppercase && "font-mono text-[0.88em] uppercase tracking-[0.16em]",
        className,
      )}
      {...props}
    >
      mouvadah
    </span>
  );
}

export interface MouvadahLockupProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof lockupVariants> {
  uppercase?: boolean;
}

export function MouvadahLockup({
  className,
  size = "md",
  uppercase,
  ...props
}: MouvadahLockupProps) {
  const resolvedSize = size ?? "md";
  return (
    <span
      className={cn(lockupVariants({ size: resolvedSize }), className)}
      aria-label="Mouvadah"
      {...props}
    >
      <MouvadahMark className={markSize[resolvedSize]} />
      <MouvadahWordmark uppercase={uppercase} aria-hidden="true" />
    </span>
  );
}
