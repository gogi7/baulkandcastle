import { useQuery } from '@tanstack/react-query'
import Card from '../components/common/Card'
import { LoadingPage } from '../components/common/Loading'

interface TableInfo {
  name: string
  rows: number
}

interface LatestInsert {
  property_id: string
  address?: string
  suburb?: string
  first_seen?: string
  date?: string
  status?: string
  price_display?: string
  scraped_at?: string
  sold_date_iso?: string
}

interface DailySummary {
  date: string
  new_count: number
  sold_count: number
  adj_count: number
}

interface MonthlyDistribution {
  month: string
  count: number
}

interface DbStats {
  tables: TableInfo[]
  properties: {
    total: number
    first_seen_range: { earliest: string | null; latest: string | null }
  }
  listing_history: {
    scrape_date_range: { earliest: string | null; latest: string | null }
    status_breakdown: Record<string, number>
  }
  sold_data: {
    sold_date_range: { earliest: string | null; latest: string | null }
    monthly_distribution: MonthlyDistribution[]
  }
  active_for_sale: number
  latest_inserts: {
    properties: LatestInsert[]
    listing_history: LatestInsert[]
    sold: LatestInsert[]
  }
  daily_summary: DailySummary[]
  data_model_info: Record<string, string>
}

async function fetchDbStats(): Promise<DbStats> {
  const response = await fetch('/api/db-stats')
  const data = await response.json()
  if (data.status !== 'success') throw new Error(data.error)
  return data
}

export default function DatabasePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['db-stats'],
    queryFn: fetchDbStats,
    refetchInterval: 30000, // Refresh every 30s
  })

  if (isLoading) return <LoadingPage />
  if (error) return <div className="text-red-600">Error loading database stats</div>
  if (!data) return null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Database Stats</h1>
        <p className="text-gray-500">Raw database validation and debugging info</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-primary-600">{data.properties.total.toLocaleString()}</div>
            <div className="text-sm text-gray-500">Total Properties</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">{data.active_for_sale.toLocaleString()}</div>
            <div className="text-sm text-gray-500">Active For Sale</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-orange-600">{data.listing_history.status_breakdown['sold'] || 0}</div>
            <div className="text-sm text-gray-500">Total Sold Records</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600">{data.tables.reduce((sum, t) => sum + t.rows, 0).toLocaleString()}</div>
            <div className="text-sm text-gray-500">Total DB Rows</div>
          </div>
        </Card>
      </div>

      {/* Table Row Counts */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Table Row Counts</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {data.tables.map((table) => (
            <div key={table.name} className="bg-gray-50 p-3 rounded-lg">
              <div className="text-sm font-mono text-gray-600">{table.name}</div>
              <div className="text-xl font-bold">{table.rows.toLocaleString()}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Date Ranges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-lg font-semibold mb-4">Date Ranges</h2>
          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-500">Scraper Running Since</div>
              <div className="font-mono">{data.properties.first_seen_range.earliest || 'N/A'}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Latest Scrape Date</div>
              <div className="font-mono">{data.listing_history.scrape_date_range.latest || 'N/A'}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Sold Data Range (from Domain)</div>
              <div className="font-mono">
                {data.sold_data.sold_date_range.earliest || 'N/A'} → {data.sold_data.sold_date_range.latest || 'N/A'}
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold mb-4">Status Breakdown</h2>
          <div className="space-y-2">
            {Object.entries(data.listing_history.status_breakdown).map(([status, count]) => (
              <div key={status} className="flex justify-between items-center">
                <span className="capitalize">{status}</span>
                <span className="font-mono font-bold">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Monthly Sold Distribution */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Monthly Sold Distribution</h2>
        <div className="overflow-x-auto">
          <div className="flex gap-2 min-w-max">
            {data.sold_data.monthly_distribution.map((m) => (
              <div key={m.month} className="text-center">
                <div className="bg-orange-100 rounded-t px-3 py-1">
                  <div className="text-lg font-bold text-orange-700">{m.count}</div>
                </div>
                <div className="bg-gray-100 rounded-b px-3 py-1 text-xs font-mono">{m.month}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Daily Summary */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Daily Summary (Last 10 Days)</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-right">New</th>
                <th className="px-4 py-2 text-right">Sold/Gone</th>
                <th className="px-4 py-2 text-right">Adjusted</th>
              </tr>
            </thead>
            <tbody>
              {data.daily_summary.map((day) => (
                <tr key={day.date} className="border-t">
                  <td className="px-4 py-2 font-mono">{day.date}</td>
                  <td className="px-4 py-2 text-right text-green-600">+{day.new_count}</td>
                  <td className="px-4 py-2 text-right text-red-600">-{day.sold_count}</td>
                  <td className="px-4 py-2 text-right text-blue-600">{day.adj_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Latest Inserts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <h2 className="text-lg font-semibold mb-4">Latest Properties Added</h2>
          <div className="space-y-2 text-sm">
            {data.latest_inserts.properties.map((p, i) => (
              <div key={i} className="bg-gray-50 p-2 rounded">
                <div className="font-medium truncate">{p.address}</div>
                <div className="text-gray-500 text-xs">{p.suburb} · {p.first_seen}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold mb-4">Latest Listing Updates</h2>
          <div className="space-y-2 text-sm">
            {data.latest_inserts.listing_history.map((h, i) => (
              <div key={i} className="bg-gray-50 p-2 rounded">
                <div className="flex justify-between">
                  <span className="font-mono text-xs">{h.property_id?.substring(0, 12)}...</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${h.status === 'sold' ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
                    {h.status}
                  </span>
                </div>
                <div className="text-gray-500 text-xs">{h.price_display} · {h.date}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold mb-4">Latest Sold</h2>
          <div className="space-y-2 text-sm">
            {data.latest_inserts.sold.map((s, i) => (
              <div key={i} className="bg-gray-50 p-2 rounded">
                <div className="font-medium truncate">{s.address}</div>
                <div className="text-gray-500 text-xs">{s.price_display} · Sold {s.sold_date_iso}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Data Model Info */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Data Model Reference</h2>
        <div className="space-y-3 text-sm">
          {Object.entries(data.data_model_info).map(([key, value]) => (
            <div key={key} className="bg-blue-50 p-3 rounded">
              <div className="font-semibold text-blue-800 capitalize">{key.replace(/_/g, ' ')}</div>
              <div className="text-blue-700">{value}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
