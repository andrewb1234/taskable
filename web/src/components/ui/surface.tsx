import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const surfaceVariants = cva("border text-surface-foreground", {
  variants: {
    tone: {
      default: "border-border bg-surface",
      elevated: "border-border bg-surface-elevated shadow-sm",
      subtle: "border-transparent bg-surface-subtle",
      marketing:
        "border-brand-sandstone/25 bg-brand-ink text-brand-paper shadow-sm",
    },
    radius: {
      none: "rounded-none",
      sm: "rounded-sm",
      md: "rounded-md",
      lg: "rounded-lg",
    },
    padding: {
      none: "p-0",
      sm: "p-3",
      md: "p-4",
      lg: "p-6",
    },
  },
  defaultVariants: {
    tone: "default",
    radius: "md",
    padding: "md",
  },
});

export interface SurfaceProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof surfaceVariants> {}

export function Surface({
  className,
  tone,
  radius,
  padding,
  ...props
}: SurfaceProps) {
  return (
    <div
      className={cn(surfaceVariants({ tone, radius, padding }), className)}
      {...props}
    />
  );
}

export { surfaceVariants };
