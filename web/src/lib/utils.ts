import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn-style class name merger. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
