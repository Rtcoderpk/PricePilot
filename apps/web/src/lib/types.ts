// Type definitions matching the PricePilot API response schemas (services/api).

export type ProviderAvailability = "available" | "unavailable";

export interface ProductIdentifierRef {
  type: string;
  value: string;
}

export interface RawOffer {
  provider: string;
  title: string;
  url?: string | null;
  price_amount?: number | null;
  price_currency: string;
  availability?: string | null;
  data_source: string;
  is_fixture: boolean;
  brand?: string | null;
  model?: string | null;
  quantity?: string | null;
  storage?: string | null;
  color?: string | null;
  identifiers: ProductIdentifierRef[];
  raw: Record<string, unknown>;
}

export interface PriceInsight {
  current: number | null;
  lowest_90d: number | null;
  avg_90d: number | null;
  currency: string;
  sample_count: number;
}

export interface ProductResult {
  canonical_product_id: string;
  name: string;
  brand?: string | null;
  category?: string | null;
  description?: string | null;
  image_url?: string | null;
  variant?: Record<string, unknown>;
  match_confidence?: number;
  match_method?: string;
  offers: RawOffer[];
  price_insight: PriceInsight | null;
  is_fixture: boolean;
}

export interface ProviderStatus {
  name: string;
  availability: ProviderAvailability;
  reason?: string | null;
}

export interface SearchResponse {
  query: string;
  products: ProductResult[];
  providers: ProviderStatus[];
  total: number;
  generated_at?: string | null;
  notice?: string | null;
}

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}