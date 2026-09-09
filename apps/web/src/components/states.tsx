import type { LucideIcon } from "lucide-react";
import { PackageX, AlertTriangle, XCircle, Loader2, Info } from "lucide-react";

/**
 * Shared, honest UI state blocks. These never fabricate content — they
 * describe exactly what the data layer reported (empty, error, unavailable,
 * insufficient). All live in one file so every page renders these states
 * consistently.
 */

interface StateBlockProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

function StateBlock({
  icon: Icon,
  tone,
  title,
  description,
  action,
  className,
}: StateBlockProps & { icon: LucideIcon; tone: "default" | "muted" | "destructive" | "warning" }) {
  const toneClasses: Record<typeof tone, string> = {
    default: "text-foreground",
    muted: "text-muted-foreground",
    destructive: "text-destructive",
    warning: "text-amber-600",
  };
  return (
    <div
      className={`flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center ${className ?? ""}`}
      role="status"
    >
      <Icon aria-hidden className={`h-8 w-8 ${toneClasses[tone]}`} />
      <p className="font-medium">{title}</p>
      {description ? <p className="max-w-md text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function EmptyState(props: StateBlockProps) {
  return <StateBlock icon={PackageX} tone="muted" {...props} />;
}

export function ErrorState(props: StateBlockProps) {
  return <StateBlock icon={XCircle} tone="destructive" {...props} />;
}

export function WarnState(props: StateBlockProps) {
  return <StateBlock icon={AlertTriangle} tone="warning" {...props} />;
}

export function InfoState(props: StateBlockProps) {
  return <StateBlock icon={Info} tone="muted" {...props} />;
}

/** Provider unavailable — never claim data exists when the provider is down. */
export function ProviderUnavailable(props: StateBlockProps) {
  return (
    <StateBlock
      icon={AlertTriangle}
      tone="warning"
      title={props.title ?? "External data provider unavailable"}
      description={
        props.description ??
        "The search/price provider could not be reached. No fabricated data is shown — please try again later."
      }
      action={props.action}
    />
  );
}

/** Not enough real observations for statistics/charts. */
export function InsufficientData(props: StateBlockProps) {
  return (
    <StateBlock
      icon={Info}
      tone="muted"
      title={props.title ?? "Not enough historical data yet"}
      description={
        props.description ??
        "Price history is collected over time as real observations. Once enough samples exist, charts and analytics will appear here."
      }
    />
  );
}

/** Loading skeleton usable anywhere. */
export function LoadingBlock({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className ?? ""}`} aria-busy="true" aria-live="polite">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`animate-pulse rounded-md bg-muted ${i === 0 ? "h-5 w-2/3" : i === 1 ? "h-4 w-full" : "h-4 w-4/5"}`}
        />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function InlineSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" aria-live="polite" className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
      <span>{label}</span>
    </span>
  );
}