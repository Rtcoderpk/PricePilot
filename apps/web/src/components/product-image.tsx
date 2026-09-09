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
    <Image
      src={src}
      alt={alt}
      width={112}
      height={112}
      loading="lazy"
      className={`h-28 w-28 rounded-md object-cover ${className ?? ""}`}
    />
  );
}