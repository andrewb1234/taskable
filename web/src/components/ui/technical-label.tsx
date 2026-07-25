import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type TechnicalLabelProps = HTMLAttributes<HTMLSpanElement>;

export function TechnicalLabel({
  className,
  ...props
}: TechnicalLabelProps) {
  return <span className={cn("technical-label", className)} {...props} />;
}
