import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        outline: "text-foreground",
        todo:
          "border-status-todo-border bg-status-todo text-status-todo-foreground",
        inprogress:
          "border-status-progress-border bg-status-progress text-status-progress-foreground",
        blocked:
          "border-status-blocked-border bg-status-blocked text-status-blocked-foreground",
        review:
          "border-status-review-border bg-status-review text-status-review-foreground",
        done:
          "border-status-done-border bg-status-done text-status-done-foreground",
        human:
          "border-actor-human-border bg-actor-human text-actor-human-foreground",
        agent:
          "border-actor-agent-border bg-actor-agent text-actor-agent-foreground",
        unassigned:
          "border-actor-unassigned-border bg-actor-unassigned text-actor-unassigned-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
