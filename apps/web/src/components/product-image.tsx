import Image from "next/image";

export function ProductImage({
  src,
  alt,
  className,
}: {
  src?: string | null;
  alt: string;
  className?: string;
}) {
  if (!src) {
    return (
      <div
        className={`flex h-28 w-28 items-center justify-center rounded-md bg-muted text-xs text-muted-foreground ${className ?? ""}`}
      >
        no image
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} loading="lazy" className={`h-28 w-28 rounded-md object-cover ${className ?? ""}`} />
  );
}