import { TrendingUp, TrendingDown, Clock, Database, BarChart3, Home, AlertCircle } from 'lucide-react'
import Card from '../common/Card'
import { useAdminSummary } from '../../hooks/useTools'
import { formatRelativeDate, formatPrice, formatPercent, getFreshnessAgeDays } from '../../utils/formatters'

function FreshnessBadge({ dateStr, label }: { dateStr: string | null; label: string }) {
  const days = getFreshnessAgeDays(dateStr)
  const isStale = days !== null && days > 7
  const isVeryStale = days !== null && days > 30

  let colorClasses = 'bg-green-100 text-green-700'
  if (isVeryStale) {
    colorClasses = 'bg-red-100 text-red-700'
  } else if (isStale) {
    colorClasses = 'bg-amber-100 text-amber-700'
  }

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-xs font-medium px-2 py-0.5 rounded ${colorClasses}`}>
        {dateStr ? formatRelativeDate(dateStr) : 'Never'}
      </span>
    </div>
  )
}

function CoverageBar({ label, value, total, percentage }: { label: string; value: number; total: number; percentage: number }) {
  const barColor = percentage >= 90 ? 'bg-green-500' : percentage >= 50 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-600">{label}</span>
        <span className="text-sm font-medium text-gray-900">
          {value}/{total} ({formatPercent(percentage, 0)})
        </span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${Math.min(percentage, 100)}%` }} />
      </div>
    </div>
  )
}

export default function AdminSummaryCards() {
  const { data: summary, isLoading, error } = useAdminSummary()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} padding="sm">
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-24 mb-3" />
              <div className="h-8 bg-gray-200 rounded w-16 mb-2" />
              <div className="h-3 bg-gray-200 rounded w-32" />
            </div>
          </Card>
        ))}
      </div>
    )
  }

  if (error || !summary) {
    return (
      <Card padding="sm" className="mb-6">
        <div className="flex items-center gap-2 text-amber-600">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">Unable to load summary data</span>
        </div>
      </Card>
    )
  }

  const { freshness, data_quality, last_scrape, daily_changes } = summary
  const hasChangesToday = daily_changes.new_count > 0 || daily_changes.sold_count > 0 || daily_changes.adjusted_count > 0

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* Latest Scrape Card */}
      <Card padding="sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-blue-100 rounded">
            <BarChart3 className="w-4 h-4 text-blue-600" />
          </div>
          <h3 className="font-medium text-gray-900">Today's Changes</h3>
        </div>

        {hasChangesToday ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-green-500" />
                <span className="text-sm text-gray-600">New listings</span>
              </div>
              <span className="text-lg font-semibold text-green-600">+{daily_changes.new_count}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <TrendingDown className="w-3.5 h-3.5 text-red-500" />
                <span className="text-sm text-gray-600">Sold/Gone</span>
              </div>
              <span className="text-lg font-semibold text-red-600">-{daily_changes.sold_count}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5 text-amber-500" />
                <span className="text-sm text-gray-600">Adjusted</span>
              </div>
              <span className="text-lg font-semibold text-amber-600">{daily_changes.adjusted_count}</span>
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-gray-500 text-sm">No changes today</p>
            {last_scrape?.completed_at && (
              <p className="text-xs text-gray-400 mt-1">Last scrape: {formatRelativeDate(last_scrape.completed_at)}</p>
            )}
          </div>
        )}
      </Card>

      {/* Active Listings Card */}
      <Card padding="sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-purple-100 rounded">
            <Home className="w-4 h-4 text-purple-600" />
          </div>
          <h3 className="font-medium text-gray-900">Active Listings</h3>
        </div>

        <div className="text-3xl font-bold text-gray-900 mb-1">{data_quality.total_for_sale}</div>
        <p className="text-sm text-gray-500">
          Avg price: {formatPrice(data_quality.avg_price, true)}
        </p>
        {last_scrape?.summary && (
          <p className="text-xs text-gray-400 mt-2 truncate" title={last_scrape.summary}>
            {last_scrape.summary}
          </p>
        )}
      </Card>

      {/* Data Freshness Card */}
      <Card padding="sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-green-100 rounded">
            <Clock className="w-4 h-4 text-green-600" />
          </div>
          <h3 className="font-medium text-gray-900">Data Freshness</h3>
        </div>

        <div className="space-y-0.5">
          <FreshnessBadge dateStr={freshness.listings} label="Listings" />
          <FreshnessBadge dateStr={freshness.domain_estimates} label="Domain Est." />
          <FreshnessBadge dateStr={freshness.xgboost_predictions} label="XGBoost" />
        </div>
      </Card>

      {/* Data Quality Card */}
      <Card padding="sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-amber-100 rounded">
            <Database className="w-4 h-4 text-amber-600" />
          </div>
          <h3 className="font-medium text-gray-900">Estimate Coverage</h3>
        </div>

        <div className="space-y-1">
          <CoverageBar
            label="Domain"
            value={data_quality.with_domain_estimate}
            total={data_quality.total_for_sale}
            percentage={data_quality.domain_coverage_pct}
          />
          <CoverageBar
            label="XGBoost"
            value={data_quality.with_xgboost_prediction}
            total={data_quality.total_for_sale}
            percentage={data_quality.xgboost_coverage_pct}
          />
        </div>
      </Card>
    </div>
  )
}
