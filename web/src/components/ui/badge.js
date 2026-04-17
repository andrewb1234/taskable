import { jsx as _jsx } from "react/jsx-runtime";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
const badgeVariants = cva("inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors", {
    variants: {
        variant: {
            default: "border-transparent bg-primary text-primary-foreground",
            secondary: "border-transparent bg-secondary text-secondary-foreground",
            outline: "text-foreground",
            todo: "border-transparent bg-muted text-muted-foreground",
            inprogress: "border-transparent bg-blue-500/20 text-blue-300",
            blocked: "border-transparent bg-red-500/20 text-red-300",
            review: "border-transparent bg-amber-500/20 text-amber-200",
            done: "border-transparent bg-emerald-500/20 text-emerald-300",
            human: "border-transparent bg-sky-500/20 text-sky-200",
            agent: "border-transparent bg-fuchsia-500/20 text-fuchsia-200",
            unassigned: "border-transparent bg-muted text-muted-foreground",
        },
    },
    defaultVariants: {
        variant: "default",
    },
});
export function Badge({ className, variant, ...props }) {
    return (_jsx("div", { className: cn(badgeVariants({ variant }), className), ...props }));
}
