import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ComingSoonCard({
  title,
  description,
  phase,
  relatedHref,
}: {
  title: string;
  description: string;
  phase: string;
  relatedHref?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription>
          Planned for {phase} — not implemented yet.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        <p>{description}</p>
        {relatedHref ? (
          <Link href={relatedHref} className="mt-2 inline-block text-primary underline">
            Try a live search →
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}