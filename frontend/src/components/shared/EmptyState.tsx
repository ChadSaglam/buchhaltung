import type { ReactNode } from "react";
import { Inbox, type LucideIcon } from "lucide-react";

interface Props {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  /**
   * Heading level. `h2` by default — an empty state usually stands in for a
   * whole page section, directly under the page `<h1>`, and the `<h3>` this
   * used to render skipped a level (axe `heading-order`). Pass `as="h3"` when
   * it sits inside a card or section that already has its own `<h2>`.
   */
  as?: "h2" | "h3";
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, as: Heading = "h2" }: Props) {
  return (
    <div
      role="status"
      aria-label={title}
      className="flex flex-col items-center justify-center px-6 py-16 text-center"
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <Icon className="h-7 w-7" aria-hidden="true" />
      </div>
      <Heading className="mt-4 text-base font-semibold text-foreground">{title}</Heading>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
