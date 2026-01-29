import { useState } from 'react'
import { Wrench } from 'lucide-react'
import { useTools, useRunTool, useExecutions } from '../hooks/useTools'
import ToolCard from '../components/tools/ToolCard'
import ExecutionHistory from '../components/tools/ExecutionHistory'
import ExecutionModal from '../components/tools/ExecutionModal'
import AdminSummaryCards from '../components/tools/AdminSummaryCards'
import Card from '../components/common/Card'
import { LoadingPage } from '../components/common/Loading'
import type { Tool } from '../types/tools'

export default function ToolsPage() {
  const { data: tools, isLoading: toolsLoading } = useTools()
  const { data: executions, isLoading: executionsLoading } = useExecutions({ limit: 15 })
  const runToolMutation = useRunTool()
  const [selectedExecution, setSelectedExecution] = useState<number | null>(null)

  const handleRunTool = (toolId: string, flags?: Record<string, unknown>) => {
    runToolMutation.mutate({ toolId, request: flags ? { flags } : undefined })
  }

  // Check if a tool is currently running
  const isToolRunning = (toolId: string): boolean => {
    return (
      runToolMutation.isPending ||
      (executions?.some((e) => e.tool_id === toolId && (e.status === 'running' || e.status === 'pending')) ?? false)
    )
  }

  // Group tools by category
  const toolsByCategory = tools?.reduce(
    (acc, tool) => {
      const category = tool.category || 'Other'
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category].push(tool)
      return acc
    },
    {} as Record<string, Tool[]>
  )

  if (toolsLoading) {
    return <LoadingPage />
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Wrench className="w-6 h-6" />
          Tools Admin
        </h1>
        <p className="text-gray-500">
          Manage and run data collection scripts, ML training, and batch processing tools
        </p>
      </div>

      {/* Admin Summary Dashboard */}
      <AdminSummaryCards />

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tools section - takes 2 columns */}
        <div className="lg:col-span-2 space-y-6">
          {toolsByCategory &&
            Object.entries(toolsByCategory).map(([category, categoryTools]) => (
              <div key={category}>
                <h2 className="text-lg font-semibold text-gray-800 mb-3">{category}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {categoryTools.map((tool) => (
                    <ToolCard
                      key={tool.id}
                      tool={tool}
                      onRun={handleRunTool}
                      isRunning={isToolRunning(tool.id)}
                    />
                  ))}
                </div>
              </div>
            ))}

          {!tools?.length && (
            <Card>
              <div className="text-center py-8 text-gray-500">
                <Wrench className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No tools available</p>
              </div>
            </Card>
          )}
        </div>

        {/* Execution history sidebar */}
        <div className="lg:col-span-1">
          <Card padding="sm">
            <h2 className="text-lg font-semibold text-gray-800 px-2 py-2">Recent Executions</h2>
            <div className="mt-2">
              {executionsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : (
                <ExecutionHistory
                  executions={executions || []}
                  onViewDetails={(execution) => setSelectedExecution(execution.id)}
                />
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Execution detail modal */}
      {selectedExecution && (
        <ExecutionModal
          executionId={selectedExecution}
          onClose={() => setSelectedExecution(null)}
        />
      )}
    </div>
  )
}
