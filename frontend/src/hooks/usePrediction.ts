import { useMutation, useQuery } from '@tanstack/react-query'
import { predict, fetchModelInfo, checkHealth } from '../api/predictions'
import type { PredictionInput } from '../types/prediction'

export function usePrediction() {
  return useMutation({
    mutationFn: (input: PredictionInput) => predict(input),
  })
}

export function useModelInfo() {
  return useQuery({
    queryKey: ['modelInfo'],
    queryFn: fetchModelInfo,
    staleTime: 30 * 60 * 1000, // 30 minutes
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 60 * 1000, // Check every minute
  })
}
