import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-6xl flex-col items-center justify-center gap-3 px-4 py-10 text-center">
      <h1 className="text-2xl font-bold tracking-tight">Page not found</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        The page you requested does not exist. Use search to find real products.
      </p>
      <Link href="/" className="text-sm font-medium text-primary underline underline-offset-2">
        Go to home
      </Link>
    </main>
  );
}