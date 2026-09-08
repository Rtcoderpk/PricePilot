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

// ---- AI shopping agent ----

export interface ShoppingIntent {
  raw_query: string;
  category?: string | null;
  product_type?: string | null;
  brands: string[];
  budget_min?: number | null;
  budget_max?: number | null;
  currency?: string | null;
  country?: string | null;
  required_features: string[];
  preferred_features: string[];
  excluded_features: string[];
  quantity?: number | null;
  condition?: string;
  use_case?: string | null;
  ranking_preference?: string;
  urgency?: string;
  uncertain_fields: string[];
}

export interface Recommendation {
  product_id: string;
  product_name: string;
  rank?: number | null;
  matches_hard_constraints: boolean;
  reasons: string[];
  deal_score?: number | null;
  best_price?: number | null;
  currency?: string | null;
  url?: string | null;
  image_url?: string | null;
  match_confidence?: number | null;
}

export interface NonProductDetail {
  product_id: string;
  status?: string;
  positive_themes?: string[];
  negative_themes?: string[];
  review_count?: number;
  label?: string;
  score?: number | null;
  reasons?: string[];
  components?: Record<string, number>;
  missing_data_warnings?: string[];
  offer_count?: number;
  lowest_offer?: number | null;
  price_position?: string;
  currency?: string | null;
  signal_labels?: string[];
  [k: string]: unknown;
}

export interface ShoppingAgentResponse {
  request_id: string;
  query: string;
  status: string;
  intent?: ShoppingIntent | null;
  products?: ProductResult[];
  recommendations?: Recommendation[];
  price_analysis?: Record<string, NonProductDetail>;
  review_analysis?: Record<string, NonProductDetail>;
  seller_analysis?: Record<string, NonProductDetail>;
  deal_scores?: Record<string, NonProductDetail>;
  warnings?: string[];
  provider_errors?: string[];
  confidence?: number;
  answer?: string | null;
}