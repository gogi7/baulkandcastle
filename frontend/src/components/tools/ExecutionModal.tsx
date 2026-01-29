import { useState } from 'react'
import {
  X,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  Ban,
  StopCircle,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Home,
  DollarSign,
} from 'lucide-react'
import { useExecution, useCancelExecution } from '../../hooks/useTools'
import type { ExecutionStatus, ScraperSummaryJson } from '../../types/tools'
import Button from '../common/Button'
import { formatRelativeDate, formatPrice } from '../../utils/formatters'

interface ExecutionModalProps {
  executionId: number
  onClose: () => void
}

// Check if execution has been running too long (matches hook timeout)
const EXECUTION_POLL_TIMEOUT_MS = 10 * 60 * 1000

function isExecutionTimedOut(startedAt: string | null): boolean {
  if (!startedAt) return false
  const elapsedMs = Date.now() - new Date(startedAt).getTime()
  return elapsedMs > EXECUTION_POLL_TIMEOUT_MS
}

function StatusIcon({ status, className = 'w-5 h-5' }: { status: ExecutionStatus; className?: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle className={`${className} text-green-500`} />
    case 'failed':
      return <XCircle className={`${className} text-red-500`} />
    case 'running':
      return <Loader2 className={`${className} text-blue-500 animate-spin`} />
    case 'pending':
      return <Clock className={`${className} text-yellow-500`} />
    case 'cancelled':
      return <Ban className={`${className} text-gray-400`} />
    default:
      return null
  }
}

// Collapsible section component
function CollapsibleSection({
  title,
  count,
  icon: Icon,
  iconColor,
  children,
  defaultOpen = false,
}: {
  title: string
  count: number
  icon: React.ElementType
  iconColor: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  if (count === 0) return null

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <span className="text-sm font-medium text-gray-700">{title}</span>
          <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">{count}</span>
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {isOpen && <div className="p-3 space-y-2 max-h-48 overflow-y-auto">{children}</div>}
    </div>
  )
}

// Scraper details component
function ScraperDetails({ summary }: { summary: ScraperSummaryJson }) {
  const { daily_changes, current_stats, details } = summary.scraper_summary

  return (
    <div className="space-y-4">
      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-600">+{daily_changes.new_count}</div>
          <div className="text-xs text-green-700">New Listings</div>
        </div>
        <div className="bg-red-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-red-600">-{daily_changes.sold_count}</div>
          <div className="text-xs text-red-700">Sold/Gone</div>
        </div>
        <div className="bg-amber-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-amber-600">{daily_changes.adjusted_count}</div>
          <div className="text-xs text-amber-700">Adjusted</div>
        </div>
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-600">{current_stats.total_for_sale}</div>
          <div className="text-xs text-blue-700">Active Total</div>
        </div>
      </div>

      {/* Detailed Sections */}
      <div className="space-y-2">
        {/* New Listings */}
        <CollapsibleSection
          title="New Listings"
          count={details.new_listings.length}
          icon={TrendingUp}
          iconColor="text-green-500"
          defaultOpen={details.new_listings.length > 0 && details.new_listings.length <= 5}
        >
          {details.new_listings.map((item, idx) => (
            <div key={idx} className="flex items-start justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{item.address}</div>
                <div className="text-xs text-gray-500">
                  {item.suburb} &bull; {item.beds}b {item.baths}ba {item.cars}c &bull; {item.property_type || 'Unknown'}
                </div>
              </div>
              <div className="text-sm font-medium text-green-600 ml-2 whitespace-nowrap">
                {item.price || formatPrice(item.price_value, true)}
              </div>
            </div>
          ))}
        </CollapsibleSection>

        {/* Sold/Gone */}
        <CollapsibleSection
          title="Sold / Gone"
          count={details.sold_gone.length}
          icon={TrendingDown}
          iconColor="text-red-500"
          defaultOpen={details.sold_gone.length > 0 && details.sold_gone.length <= 5}
        >
          {details.sold_gone.map((item, idx) => (
            <div key={idx} className="flex items-start justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{item.address}</div>
                <div className="text-xs text-gray-500">{item.suburb}</div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    item.type === 'sold' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {item.type === 'sold' ? 'Sold' : 'Disappeared'}
                </span>
                <span className="text-sm text-gray-600">{item.price || formatPrice(item.price_value, true)}</span>
              </div>
            </div>
          ))}
        </CollapsibleSection>

        {/* Price Changes */}
        <CollapsibleSection
          title="Price Changes"
          count={details.price_changes.length}
          icon={DollarSign}
          iconColor="text-amber-500"
          defaultOpen={details.price_changes.length > 0}
        >
          {details.price_changes.map((item, idx) => (
            <div key={idx} className="py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{item.address}</div>
                  <div className="text-xs text-gray-500">{item.suburb}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-gray-500">{item.old_price}</span>
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">{item.new_price}</span>
                {item.diff !== 0 && (
                  <span className={`text-xs font-medium ${item.diff < 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ({item.diff < 0 ? '' : '+'}
                    {formatPrice(item.diff, true)})
                  </span>
                )}
              </div>
            </div>
          ))}
        </CollapsibleSection>

        {/* Guides Revealed */}
        <CollapsibleSection
          title="Auction Guides Revealed"
          count={details.guides_revealed.length}
          icon={Home}
          iconColor="text-purple-500"
          defaultOpen={details.guides_revealed.length > 0}
        >
          {details.guides_revealed.map((item, idx) => (
            <div key={idx} className="py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{item.address}</div>
                  <div className="text-xs text-gray-500">{item.suburb}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-gray-400 italic">{item.old_price || 'No guide'}</span>
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <span className="text-sm font-medium text-purple-600">{item.new_price}</span>
              </div>
            </div>
          ))}
        </CollapsibleSection>

        {/* All Adjustments (fallback for changes not in other categories) */}
        <CollapsibleSection
          title="All Adjustments"
          count={details.all_adjustments?.length || 0}
          icon={AlertTriangle}
          iconColor="text-gray-500"
          defaultOpen={(details.all_adjustments?.length || 0) > 0 && (details.all_adjustments?.length || 0) <= 5}
        >
          {details.all_adjustments?.map((item, idx) => (
            <div key={idx} className="py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{item.address}</div>
                  <div className="text-xs text-gray-500">{item.suburb}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="text-xs text-gray-500 max-w-[45%] truncate" title={item.old_price}>
                  {item.old_price || '(empty)'}
                </span>
                <ArrowRight className="w-3 h-3 text-gray-400 flex-shrink-0" />
                <span className="text-xs font-medium text-gray-700 max-w-[45%] truncate" title={item.new_price}>
                  {item.new_price || '(empty)'}
                </span>
              </div>
              {item.old_status !== item.new_status && (
                <div className="text-xs text-amber-600 mt-0.5">
                  Status: {item.old_status} → {item.new_status}
                </div>
              )}
            </div>
          ))}
        </CollapsibleSection>
      </div>

      {/* Current Stats Footer */}
      <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
        Total tracked: {current_stats.total_tracked} | Avg price: {formatPrice(current_stats.avg_price, true)} | Catchment:{' '}
        {current_stats.excelsior_catchment_sale}
      </div>
    </div>
  )
}

export default function ExecutionModal({ executionId, onClose }: ExecutionModalProps) {
  const { data: execution, isLoading } = useExecution(executionId)
  const cancelMutation = useCancelExecution()

  const handleCancel = () => {
    cancelMutation.mutate(executionId)
  }

  const canCancel = execution?.status === 'running' || execution?.status === 'pending'

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={onClose}
        />

        <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-3xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              {execution && <StatusIcon status={execution.status} />}
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {execution?.tool_name || 'Execution'} #{executionId}
                </h3>
                {execution && (
                  <p className="text-sm text-gray-500">
                    {execution.status === 'running' ? (
                      <>Started {formatRelativeDate(execution.started_at || execution.created_at)}</>
                    ) : execution.completed_at ? (
                      <>Completed {formatRelativeDate(execution.completed_at)}</>
                    ) : (
                      <>Created {formatRelativeDate(execution.created_at)}</>
                    )}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 max-h-[60vh] overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            ) : execution ? (
              <div className="space-y-4">
                {/* Timeout Warning */}
                {(execution.status === 'running' || execution.status === 'pending') &&
                  isExecutionTimedOut(execution.started_at) && (
                    <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-amber-800">Execution running longer than expected</p>
                        <p className="text-sm text-amber-700 mt-1">
                          This execution has been running for over 10 minutes. It may have stalled or be processing a large dataset.
                          You can cancel it or check the server logs.
                        </p>
                      </div>
                    </div>
                  )}

                {/* Scraper Detailed Summary */}
                {execution.summary_json?.scraper_summary && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Scrape Results</h4>
                    <ScraperDetails summary={execution.summary_json} />
                  </div>
                )}

                {/* Text Summary (shown if no JSON or for non-scraper tools) */}
                {execution.summary && !execution.summary_json?.scraper_summary && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Summary</h4>
                    <p className="text-sm text-gray-900 bg-gray-50 rounded p-3">{execution.summary}</p>
                  </div>
                )}

                {/* Flags */}
                {execution.flags && Object.keys(execution.flags).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Flags</h4>
                    <div className="bg-gray-50 rounded p-3">
                      <code className="text-xs text-gray-700">
                        {Object.entries(execution.flags)
                          .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
                          .join(' ')}
                      </code>
                    </div>
                  </div>
                )}

                {/* Exit Code */}
                {execution.exit_code !== null && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Exit Code</h4>
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-sm font-mono ${
                        execution.exit_code === 0
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {execution.exit_code}
                    </span>
                  </div>
                )}

                {/* Output */}
                {execution.stdout && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Output</h4>
                    <pre className="text-xs text-gray-700 bg-gray-900 text-gray-100 rounded p-3 overflow-x-auto max-h-64 whitespace-pre-wrap">
                      {execution.stdout}
                    </pre>
                  </div>
                )}

                {/* Errors */}
                {execution.stderr && (
                  <div>
                    <h4 className="text-sm font-medium text-red-700 mb-1">Errors</h4>
                    <pre className="text-xs bg-red-50 text-red-700 rounded p-3 overflow-x-auto max-h-64 whitespace-pre-wrap">
                      {execution.stderr}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">Execution not found</p>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-200 bg-gray-50">
            {canCancel && (
              <Button
                variant="outline"
                onClick={handleCancel}
                loading={cancelMutation.isPending}
              >
                <StopCircle className="w-4 h-4 mr-1.5" />
                Cancel Execution
              </Button>
            )}
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
