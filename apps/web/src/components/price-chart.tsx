// Real price chart — plots only actual observations. Never fabricates points.
export function PriceChart({
  points,
  currency,
}: {
  points: Array<{ amount: number; observed_at: string }>;
  currency?: string | null;
}) {
  if (points.length < 2) {
    return (
      <div className="rounded-md border border-dashed bg-muted/20 p-6 text-center text-sm text-muted-foreground">
        Not enough historical data yet (need at least 2 observations).
      </div>
    );
  }

  const W = 560;
  const H = 180;
  const pad = 12;
  const xs = points.map((p) => new Date(p.observed_at).getTime());
  const ys = points.map((p) => p.amount);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;

  const toX = (x: number) => pad + ((x - minX) / spanX) * (W - 2 * pad);
  const toY = (y: number) => H - pad - ((y - minY) / spanY) * (H - 2 * pad);

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(new Date(p.observed_at).getTime()).toFixed(1)},${toY(p.amount).toFixed(1)}`)
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Price history (${currency ?? ""})`}
      className="h-48 w-full rounded-md border bg-background"
    >
      <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} stroke="currentColor" strokeOpacity={0.15} />
      <polyline points={line} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" />
      {points.map((p, i) => (
        <circle key={i} cx={toX(new Date(p.observed_at).getTime())} cy={toY(p.amount)} r={3} fill="currentColor" />
      ))}
    </svg>
  );
}
