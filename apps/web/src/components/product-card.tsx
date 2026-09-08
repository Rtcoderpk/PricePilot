import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ProductImage } from "@/components/product-image";
import { BestPrice, formatPrice } from "@/components/price";
import { cn } from "@/lib/utils";
import type { ProductResult } from "@/lib/types";

interface ProductCardProps {
  product: ProductResult;
  onCompare?: (id: string) => void;
  hasFixtures?: boolean;
}

export function ProductCard({ product, onCompare, hasFixtures }: ProductCardProps) {
  const { offers, price_insight, is_fixture } = product;
  const sellers = offers.length;
  const priced = offers.filter((o) => o.price_amount != null).length;

  return (
    <Card className="flex h-full flex-col transition-shadow hover:shadow-md">
      <CardHeader className="flex-row items-start gap-4 space-y-0">
        <ProductImage src={product.image_url} alt={product.name} />
        <div className="min-w-0 flex-1">
          <CardTitle className="line-clamp-2 text-base">{product.name}</CardTitle>
          <CardDescription className="mt-1 line-clamp-2">{product.brand ?? product.category ?? "—"}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <BestPrice price={price_insight} />
          {sellers > 0 && <Badge variant="secondary">{sellers} seller{sellers > 1 ? "s" : ""}</Badge>}
          {hasFixtures || is_fixture ? (
            <Badge variant="warning">demo data</Badge>
          ) : (
            <Badge variant="outline">{offers[0]?.provider ?? "provider"}</Badge>
          )}
        </div>

        {priced > 0 && (
          <p className="text-xs text-muted-foreground">
            {priced} price{priced > 1 ? "s" : ""} · range{" "}
            {formatPrice(Math.min(...offers.map((o) => o.price_amount ?? Infinity)), price_insight?.currency)}
            {" – "}
            {formatPrice(Math.max(...offers.map((o) => o.price_amount ?? -Infinity)), price_insight?.currency)}
          </p>
        )}

        <div className="mt-auto flex items-center gap-2">
          {onCompare ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onCompare(product.canonical_product_id)}
            >
              Compare
            </Button>
          ) : null}
          {product.offers[0]?.url ? (
            <Button size="sm" variant="outline" asChild>
              <a href={product.offers[0].url} target="_blank" rel="noopener noreferrer">
                View product
              </a>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}