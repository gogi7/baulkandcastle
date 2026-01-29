import { useState } from 'react'
import { Play, Settings, CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react'
import Card from '../common/Card'
import Button from '../common/Button'
import ToolFlagForm from './ToolFlagForm'
import type { Tool, ExecutionStatus } from '../../types/tools'
import { formatRelativeDate } from '../../utils/formatters'

interface ToolCardProps {
  tool: Tool
  onRun: (toolId: string, flags?: Record<string, unknown>) => void
  isRunning: boolean
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
      return <XCircle className="w-4 h-4 text-gray-400" />
    default:
      return null
  }
}

export default function ToolCard({ tool, onRun, isRunning }: ToolCardProps) {
  const [showConfig, setShowConfig] = useState(false)
  const [flags, setFlags] = useState<Record<string, unknown>>({})

  const handleRun = () => {
    const hasFlags = Object.keys(flags).length > 0
    onRun(tool.id, hasFlags ? flags : undefined)
  }

  const handleFlagChange = (name: string, value: unknown) => {
    setFlags((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  return (
    <Card className="flex flex-col">
      <div className="flex-1">
        <h3 className="text-lg font-semibold text-gray-900">{tool.name}</h3>
        <p className="mt-1 text-sm text-gray-500">{tool.description}</p>

        {tool.last_run && (
          <div className="mt-3 flex items-center gap-2 text-sm">
            <StatusIcon status={tool.last_run.status} />
            <span className="text-gray-600">
              {tool.last_run.status === 'running' ? (
                'Running...'
              ) : tool.last_run.completed_at ? (
                <>Last run {formatRelativeDate(tool.last_run.completed_at)}</>
              ) : tool.last_run.started_at ? (
                <>Started {formatRelativeDate(tool.last_run.started_at)}</>
              ) : (
                'Pending...'
              )}
            </span>
          </div>
        )}

        {tool.last_run?.summary && tool.last_run.status !== 'running' && (
          <p className="mt-1 text-xs text-gray-400 truncate" title={tool.last_run.summary}>
            {tool.last_run.summary}
          </p>
        )}
      </div>

      {showConfig && tool.flags.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <ToolFlagForm flags={tool.flags} values={flags} onChange={handleFlagChange} />
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-gray-100 flex gap-2">
        <Button onClick={handleRun} loading={isRunning} disabled={isRunning} size="sm">
          <Play className="w-4 h-4 mr-1.5" />
          Run
        </Button>
        {tool.flags.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowConfig(!showConfig)}
            className={showConfig ? 'bg-gray-50' : ''}
          >
            <Settings className="w-4 h-4 mr-1.5" />
            {showConfig ? 'Hide Options' : 'Options'}
          </Button>
        )}
      </div>
    </Card>
  )
}
