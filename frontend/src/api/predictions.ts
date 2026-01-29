import api from './client'
import type { PredictionInput, PredictionResult, ModelInfo } from '../types/prediction'

interface PredictResponse {
  status: string
  prediction: PredictionResult
}

interface ModelInfoResponse {
  status: string
  metadata: ModelInfo
}

interface HealthResponse {
  status: string
  model_loaded: boolean
  trained_at?: string
  error?: string
}

export async function predict(input: PredictionInput): Promise<PredictionResult> {
  const { data } = await api.post<PredictResponse>('/predict', input)
  return data.prediction
}

export async function fetchModelInfo(): Promise<ModelInfo> {
  const { data } = await api.get<ModelInfoResponse>('/model-info')
  return data.metadata
}

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}
