// Tool flag definition
export interface ToolFlag {
  name: string
  type: 'boolean' | 'string' | 'number' | 'select'
  description: string
  default?: boolean | string | number | null
  options?: string[] // For select type
}

// Last run information
export interface ToolLastRun {
  execution_id: number
  status: ExecutionStatus
  started_at: string | null
  completed_at: string | null
  summary: string | null
}

// Tool definition
export interface Tool {
  id: string
  name: string
  description: string
  category: string
  script: string
  flags: ToolFlag[]
  last_run: ToolLastRun | null
}

// Execution status
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

// Scraper summary details
export interface ScraperSummaryDetails {
  new_listings: Array<{
    address: string
    suburb: string
    price: string
    price_value: number
    beds: number
    baths: number
    cars: number
    property_type: string
  }>
  sold_gone: Array<{
    address: string
    suburb: string
    price: string
    price_value: number
    type: 'sold' | 'disappeared'
  }>
  price_changes: Array<{
    address: string
    suburb: string
    old_price: string
    new_price: string
    old_value: number
    new_value: number
    diff: number
  }>
  guides_revealed: Array<{
    address: string
    suburb: string
    old_price: string
    new_price: string
    price_value: number
  }>
  all_adjustments: Array<{
    address: string
    suburb: string
    old_price: string
    new_price: string
    old_status: string
    new_status: string
  }>
}

export interface ScraperSummaryJson {
  scraper_summary: {
    date: string
    daily_changes: {
      new_count: number
      sold_count: number
      adjusted_count: number
    }
    current_stats: {
      total_for_sale: number
      avg_price: number
      total_tracked: number
      baulkham_hills_count: number
      castle_hill_count: number
      excelsior_catchment_sale: number
    }
    details: ScraperSummaryDetails
    status: string
  }
}

// Tool execution record
export interface ToolExecution {
  id: number
  tool_id: string
  tool_name: string
  status: ExecutionStatus
  flags: Record<string, unknown> | null
  started_at: string | null
  completed_at: string | null
  exit_code: number | null
  stdout?: string | null
  stderr?: string | null
  summary: string | null
  summary_json?: ScraperSummaryJson | null
  created_at: string
}

// Request types
export interface RunToolRequest {
  flags?: Record<string, unknown>
}

// Admin summary types
export interface AdminSummary {
  freshness: {
    listings: string | null
    domain_estimates: string | null
    xgboost_predictions: string | null
  }
  data_quality: {
    total_for_sale: number
    with_domain_estimate: number
    with_xgboost_prediction: number
    domain_coverage_pct: number
    xgboost_coverage_pct: number
    avg_price: number
  }
  last_scrape: {
    completed_at: string | null
    summary: string | null
    status: string | null
  } | null
  daily_changes: {
    new_count: number
    sold_count: number
    adjusted_count: number
  }
}
