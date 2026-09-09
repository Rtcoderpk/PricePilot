import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn("inline-flex items-center gap-2 text-sm text-muted-foreground", className)}
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}