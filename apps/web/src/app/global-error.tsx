"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error for observability (no secrets forwarded).
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <main className="mx-auto flex min-h-[60vh] w-full max-w-6xl flex-col items-center justify-center gap-4 px-4 py-10 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Something went wrong</h1>
          <p className="max-w-md text-sm text-muted-foreground">
            An unexpected error occurred. This is logged on the server, not sensitive to you.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => reset()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Try again
            </button>
            <Link
              href="/"
              className="rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              Go home
            </Link>
          </div>
        </main>
      </body>
    </html>
  );
}