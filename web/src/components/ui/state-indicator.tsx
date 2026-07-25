import type { HTMLAttributes } from "react";
import {
  Bot,
  Circle,
  CircleCheck,
  CircleHelp,
  CirclePause,
  CirclePlay,
  CircleUserRound,
  OctagonAlert,
  ScanEye,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  ASSIGNEE_LABELS,
  TICKET_STATUS_LABELS,
  type TicketAssignee,
  type TicketStatus,
} from "@/types";

type IndicatorIcon = LucideIcon;

const statusPresentation: Record<
  TicketStatus,
  {
    variant: "todo" | "inprogress" | "blocked" | "review" | "done";
    icon: IndicatorIcon;
  }
> = {
  TODO: { variant: "todo", icon: CirclePause },
  IN_PROGRESS: { variant: "inprogress", icon: CirclePlay },
  BLOCKED: { variant: "blocked", icon: OctagonAlert },
  REVIEW: { variant: "review", icon: ScanEye },
  DONE: { variant: "done", icon: CircleCheck },
};

const assigneePresentation: Record<
  TicketAssignee,
  {
    variant: "human" | "agent" | "unassigned";
    icon: IndicatorIcon;
  }
> = {
  HUMAN: { variant: "human", icon: CircleUserRound },
  AGENT: { variant: "agent", icon: Bot },
  UNASSIGNED: { variant: "unassigned", icon: CircleHelp },
};

export interface StateIndicatorProps extends HTMLAttributes<HTMLDivElement> {
  icon?: IndicatorIcon;
  label: string;
  variant:
    | "todo"
    | "inprogress"
    | "blocked"
    | "review"
    | "done"
    | "human"
    | "agent"
    | "unassigned";
}

export function StateIndicator({
  className,
  icon: Icon = Circle,
  label,
  variant,
  ...props
}: StateIndicatorProps) {
  return (
    <Badge
      variant={variant}
      className={cn("gap-1.5 whitespace-nowrap", className)}
      {...props}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      <span>{label}</span>
    </Badge>
  );
}

export function TicketStatusIndicator({
  status,
  className,
  ...props
}: Omit<StateIndicatorProps, "icon" | "label" | "variant"> & {
  status: TicketStatus;
}) {
  const presentation = statusPresentation[status];
  return (
    <StateIndicator
      variant={presentation.variant}
      icon={presentation.icon}
      label={TICKET_STATUS_LABELS[status]}
      className={className}
      {...props}
    />
  );
}

export function AssigneeIndicator({
  assignee,
  className,
  ...props
}: Omit<StateIndicatorProps, "icon" | "label" | "variant"> & {
  assignee: TicketAssignee;
}) {
  const presentation = assigneePresentation[assignee];
  return (
    <StateIndicator
      variant={presentation.variant}
      icon={presentation.icon}
      label={ASSIGNEE_LABELS[assignee]}
      className={className}
      {...props}
    />
  );
}
