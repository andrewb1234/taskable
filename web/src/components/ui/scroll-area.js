import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { forwardRef, } from "react";
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import { cn } from "@/lib/utils";
export const ScrollArea = forwardRef(({ className, children, ...props }, ref) => (_jsxs(ScrollAreaPrimitive.Root, { ref: ref, className: cn("relative overflow-hidden", className), ...props, children: [_jsx(ScrollAreaPrimitive.Viewport, { className: "h-full w-full rounded-[inherit]", children: children }), _jsx(ScrollBar, {}), _jsx(ScrollAreaPrimitive.Corner, {})] })));
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName;
const ScrollBar = forwardRef(({ className, orientation = "vertical", ...props }, ref) => (_jsx(ScrollAreaPrimitive.ScrollAreaScrollbar, { ref: ref, orientation: orientation, className: cn("flex touch-none select-none transition-colors", orientation === "vertical" && "h-full w-2 border-l border-l-transparent", orientation === "horizontal" &&
        "h-2 flex-col border-t border-t-transparent", className), ...props, children: _jsx(ScrollAreaPrimitive.ScrollAreaThumb, { className: "relative flex-1 rounded-full bg-border" }) })));
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName;
