export interface Property {
  property_id: string
  address: string
  suburb: string
  first_seen?: string
  url: string
  in_excelsior_catchment?: number
  price_display: string
  price_value: number
  beds: number
  baths: number
  cars: number
  land_size: string | null
  property_type: string
  agent?: string
  status?: string
  sold_date?: string
  sold_date_iso?: string
  price_per_m2?: number
  // Extended fields (only present when extended=true)
  domain_estimate_low?: number | null
  domain_estimate_mid?: number | null
  domain_estimate_high?: number | null
  xgboost_predicted_price?: number | null
  xgboost_price_low?: number | null
  xgboost_price_high?: number | null
  days_on_market?: number | null
  initial_price?: number | null
  // Timestamp fields (extended)
  domain_scraped_at?: string | null
  xgboost_predicted_at?: string | null
  listing_scraped_at?: string | null
  price_change_count?: number | null
}

export interface DataFreshness {
  listing_last_scraped: string | null
  domain_last_scraped: string | null
  xgboost_last_predicted: string | null
}

export interface PropertyFilters {
  suburb?: string
  property_type?: string
  min_price?: number
  max_price?: number
  beds?: number
  baths?: number
  min_land_size?: number
  excelsior_only?: boolean
}

export interface PropertyStats {
  total_for_sale: number
  total_sold: number
  new_this_week: number
  sold_this_week: number
  avg_price_for_sale: number
  avg_price_sold: number
  by_suburb: Record<string, { for_sale: number; sold: number }>
  by_property_type: Record<string, number>
}

export interface TrendData {
  month: string
  suburb: string
  property_type: string
  count: number
  avg_price: number
  avg_price_per_m2: number
}
