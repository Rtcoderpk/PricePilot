export function PageHeader({
  title,
  description,
  phase,
}: {
  title: string;
  description: string;
  phase?: string;
}) {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-2xl text-muted-foreground">{description}</p>
      {phase ? (
        <p className="mt-2 inline-block rounded-full border bg-muted px-3 py-0.5 text-xs text-muted-foreground">
          {phase}
        </p>
      ) : null}
    </div>
  );
}