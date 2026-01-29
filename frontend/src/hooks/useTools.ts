import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTools, runTool, fetchExecutions, fetchExecution, cancelExecution, fetchAdminSummary } from '../api/tools'
import type { RunToolRequest } from '../types/tools'

export function useTools() {
  return useQuery({
    queryKey: ['tools'],
    queryFn: fetchTools,
    refetchInterval: 5000, // Poll every 5 seconds to catch status changes
  })
}

export function useRunTool() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ toolId, request }: { toolId: string; request?: RunToolRequest }) =>
      runTool(toolId, request),
    onSuccess: () => {
      // Invalidate both tools (for last_run) and executions
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['executions'] })
    },
  })
}

export function useExecutions(params?: { limit?: number; tool_id?: string }) {
  return useQuery({
    queryKey: ['executions', params],
    queryFn: () => fetchExecutions(params),
    refetchInterval: 5000, // Poll every 5 seconds
  })
}

// Maximum time to poll for an execution (10 minutes)
const EXECUTION_POLL_TIMEOUT_MS = 10 * 60 * 1000

export function useExecution(executionId: number | null) {
  return useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => fetchExecution(executionId!),
    enabled: executionId !== null,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000

      // Stop polling if completed/failed/cancelled
      const status = data.status
      if (status !== 'running' && status !== 'pending') {
        return false
      }

      // Frontend timeout fallback: stop polling if running too long
      const startedAt = data.started_at
      if (startedAt) {
        const elapsedMs = Date.now() - new Date(startedAt).getTime()
        if (elapsedMs > EXECUTION_POLL_TIMEOUT_MS) {
          // Stop polling - execution has been running too long
          console.warn(`Execution #${executionId} polling timeout after ${Math.round(elapsedMs / 1000)}s`)
          return false
        }
      }

      // Continue polling
      return 2000
    },
  })
}

export function useCancelExecution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (executionId: number) => cancelExecution(executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['executions'] })
    },
  })
}

export function useAdminSummary() {
  return useQuery({
    queryKey: ['adminSummary'],
    queryFn: fetchAdminSummary,
    refetchInterval: 60000, // Refresh every 60 seconds
    staleTime: 30000, // Consider data stale after 30 seconds
  })
}
