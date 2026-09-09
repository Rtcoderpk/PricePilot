import { cn } from "@/lib/utils";

/** Consistent page-width wrapper. */
export function Container({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 sm:px-6", className)}>{children}</div>;
}

/** Vertical page rhythm shared by every routed page. */
export function PageContainer({ className, children }: { className?: string; children: React.ReactNode }) {
  return <Container className={cn("py-8 sm:py-10", className)}>{children}</Container>;
}