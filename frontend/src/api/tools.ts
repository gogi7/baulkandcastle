import api from './client'
import type { Tool, ToolExecution, RunToolRequest, AdminSummary } from '../types/tools'

interface ToolsResponse {
  status: string
  tools: Tool[]
}

interface ExecutionsResponse {
  status: string
  executions: ToolExecution[]
}

interface ExecutionResponse {
  status: string
  execution: ToolExecution
}

interface RunToolResponse {
  status: string
  execution_id: number
}

interface CancelResponse {
  status: string
  cancelled: boolean
}

interface AdminSummaryResponse {
  status: string
  freshness: AdminSummary['freshness']
  data_quality: AdminSummary['data_quality']
  last_scrape: AdminSummary['last_scrape']
  daily_changes: AdminSummary['daily_changes']
}

export async function fetchTools(): Promise<Tool[]> {
  const { data } = await api.get<ToolsResponse>('/tools')
  return data.tools
}

export async function runTool(toolId: string, request?: RunToolRequest): Promise<number> {
  const { data } = await api.post<RunToolResponse>(`/tools/${toolId}/run`, request || {})
  return data.execution_id
}

export async function fetchExecutions(params?: {
  limit?: number
  tool_id?: string
}): Promise<ToolExecution[]> {
  const { data } = await api.get<ExecutionsResponse>('/tools/executions', { params })
  return data.executions
}

export async function fetchExecution(executionId: number): Promise<ToolExecution> {
  const { data } = await api.get<ExecutionResponse>(`/tools/executions/${executionId}`)
  return data.execution
}

export async function cancelExecution(executionId: number): Promise<boolean> {
  const { data } = await api.post<CancelResponse>(`/tools/executions/${executionId}/cancel`)
  return data.cancelled
}

export async function fetchAdminSummary(): Promise<AdminSummary> {
  const { data } = await api.get<AdminSummaryResponse>('/admin/summary')
  return {
    freshness: data.freshness,
    data_quality: data.data_quality,
    last_scrape: data.last_scrape,
    daily_changes: data.daily_changes,
  }
}
