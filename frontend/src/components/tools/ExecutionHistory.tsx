import { CheckCircle, XCircle, Clock, Loader2, Ban, Eye } from 'lucide-react'
import type { ToolExecution, ExecutionStatus } from '../../types/tools'
import { formatRelativeDate } from '../../utils/formatters'

interface ExecutionHistoryProps {
  executions: ToolExecution[]
  onViewDetails: (execution: ToolExecution) => void
}

function StatusIcon({ status }: { status: ExecutionStatus }) {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-4 h-4 text-green-500" />
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-500" />
    case 'running':
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
    case 'pending':
      return <Clock className="w-4 h-4 text-yellow-500" />
    case 'cancelled':
      return <Ban className="w-4 h-4 text-gray-400" />
    default:
      return null
  }
}

function StatusBadge({ status }: { status: ExecutionStatus }) {
  const colors: Record<ExecutionStatus, string> = {
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
    pending: 'bg-yellow-100 text-yellow-700',
    cancelled: 'bg-gray-100 text-gray-600',
  }

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status]}`}>
      {status}
    </span>
  )
}

export default function ExecutionHistory({ executions, onViewDetails }: ExecutionHistoryProps) {
  if (executions.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No executions yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {executions.map((execution) => (
        <div
          key={execution.id}
          className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-100 hover:border-gray-200 transition-colors cursor-pointer"
          onClick={() => onViewDetails(execution)}
        >
          <StatusIcon status={execution.status} />

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm text-gray-900 truncate">
                {execution.tool_name}
              </span>
              <StatusBadge status={execution.status} />
            </div>
            <p className="text-xs text-gray-500 truncate">
              {execution.status === 'running' ? (
                <>Started {formatRelativeDate(execution.started_at || execution.created_at)}</>
              ) : execution.completed_at ? (
                <>{formatRelativeDate(execution.completed_at)}</>
              ) : (
                <>Created {formatRelativeDate(execution.created_at)}</>
              )}
              {execution.summary && execution.status !== 'running' && (
                <> - {execution.summary}</>
              )}
            </p>
          </div>

          <Eye className="w-4 h-4 text-gray-400" />
        </div>
      ))}
    </div>
  )
}
