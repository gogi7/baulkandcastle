import { useState } from 'react'
import { usePrediction, useModelInfo } from '../hooks/usePrediction'
import PredictorForm from '../components/predictor/PredictorForm'
import PredictionResult from '../components/predictor/PredictionResult'
import Card from '../components/common/Card'
import { formatPercent, formatPrice, formatDate } from '../utils/formatters'
import type { PredictionInput, PredictionResult as PredictionResultType } from '../types/prediction'

export default function PredictorPage() {
  const [result, setResult] = useState<PredictionResultType | null>(null)
  const prediction = usePrediction()
  const { data: modelInfo } = useModelInfo()

  const handleSubmit = async (input: PredictionInput) => {
    try {
      const res = await prediction.mutateAsync(input)
      setResult(res)
    } catch {
      setResult(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Property Valuation</h1>
        <p className="text-gray-500">
          Get an AI-powered property value estimate
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <PredictorForm
            onSubmit={handleSubmit}
            isLoading={prediction.isPending}
          />

          {modelInfo && (
            <Card>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Model Information
              </h3>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-gray-500">Trained</dt>
                <dd className="text-gray-900 text-right">
                  {formatDate(modelInfo.trained_at)}
                </dd>
                <dt className="text-gray-500">R² Score</dt>
                <dd className="text-gray-900 text-right">
                  {modelInfo.metrics?.r2?.toFixed(4) || '-'}
                </dd>
                <dt className="text-gray-500">MAE</dt>
                <dd className="text-gray-900 text-right">
                  {formatPrice(modelInfo.metrics?.mae)}
                </dd>
                <dt className="text-gray-500">MAPE</dt>
                <dd className="text-gray-900 text-right">
                  {formatPercent(modelInfo.metrics?.mape)}
                </dd>
                <dt className="text-gray-500">Training Samples</dt>
                <dd className="text-gray-900 text-right">
                  {modelInfo.metrics?.train_size?.toLocaleString() || '-'}
                </dd>
              </dl>
            </Card>
          )}
        </div>

        <div>
          {prediction.isError && (
            <Card className="bg-red-50 border-red-200">
              <p className="text-red-700">
                Error: {prediction.error?.message || 'Failed to get prediction'}
              </p>
            </Card>
          )}

          {result && <PredictionResult result={result} />}

          {!result && !prediction.isError && (
            <Card className="flex items-center justify-center min-h-[300px]">
              <div className="text-center text-gray-500">
                <p className="text-lg font-medium">Enter property details</p>
                <p className="text-sm">
                  Fill in the form to get an estimated value
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
