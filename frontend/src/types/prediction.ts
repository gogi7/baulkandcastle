export interface PredictionInput {
  beds: number
  bathrooms: number
  car_spaces: number
  land_size?: number
  suburb: string
  property_type: string
}

export interface PredictionResult {
  predicted_price: number
  price_range_low: number
  price_range_high: number
  confidence_level: string
  confidence_note?: string
  input_features: {
    land_size: number | null
    land_size_used: number
    has_real_land_size: boolean
    beds: number
    bathrooms: number
    car_spaces: number
    suburb: string
    property_type: string
    property_type_consolidated: string
  }
}

export interface ModelInfo {
  trained_at: string
  metrics: {
    r2: number
    mae: number
    mape: number
    train_size: number
    test_size: number
  }
  feature_importance: Record<string, number>
  type_distribution: Record<string, number>
  suburb_distribution: Record<string, number>
}
