import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
/** shadcn-style class name merger. */
export function cn(...inputs) {
    return twMerge(clsx(inputs));
}
