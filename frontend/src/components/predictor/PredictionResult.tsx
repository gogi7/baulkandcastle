import { TrendingUp, AlertCircle, Info } from 'lucide-react'
import Card from '../common/Card'
import { formatPrice, formatPriceRange } from '../../utils/formatters'
import type { PredictionResult as PredictionResultType } from '../../types/prediction'

interface PredictionResultProps {
  result: PredictionResultType
}

export default function PredictionResult({ result }: PredictionResultProps) {
  return (
    <Card>
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-50 mb-4">
          <TrendingUp className="w-8 h-8 text-primary-600" />
        </div>

        <h3 className="text-lg font-semibold text-gray-900 mb-1">
          Estimated Value
        </h3>

        <p className="text-4xl font-bold text-primary-600 mb-2">
          {formatPrice(result.predicted_price)}
        </p>

        <p className="text-sm text-gray-500 mb-4">
          Range: {formatPriceRange(result.price_range_low, result.price_range_high)}
        </p>

        {result.confidence_note && (
          <div className="flex items-start space-x-2 text-sm text-amber-600 bg-amber-50 rounded-lg p-3 mb-4">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{result.confidence_note}</span>
          </div>
        )}

        <div className="flex items-center justify-center space-x-2 text-sm text-gray-500">
          <Info className="w-4 h-4" />
          <span>{result.confidence_level}</span>
        </div>
      </div>

      <div className="mt-6 pt-6 border-t border-gray-200">
        <h4 className="text-sm font-medium text-gray-900 mb-3">
          Input Summary
        </h4>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-gray-500">Property Type</dt>
          <dd className="text-gray-900 text-right capitalize">
            {result.input_features.property_type_consolidated}
          </dd>
          <dt className="text-gray-500">Suburb</dt>
          <dd className="text-gray-900 text-right">
            {result.input_features.suburb}
          </dd>
          <dt className="text-gray-500">Bedrooms</dt>
          <dd className="text-gray-900 text-right">
            {result.input_features.beds}
          </dd>
          <dt className="text-gray-500">Bathrooms</dt>
          <dd className="text-gray-900 text-right">
            {result.input_features.bathrooms}
          </dd>
          <dt className="text-gray-500">Car Spaces</dt>
          <dd className="text-gray-900 text-right">
            {result.input_features.car_spaces}
          </dd>
          <dt className="text-gray-500">Land Size Used</dt>
          <dd className="text-gray-900 text-right">
            {result.input_features.land_size_used}m²
            {!result.input_features.has_real_land_size && (
              <span className="text-gray-400 ml-1">(imputed)</span>
            )}
          </dd>
        </dl>
      </div>
    </Card>
  )
}
