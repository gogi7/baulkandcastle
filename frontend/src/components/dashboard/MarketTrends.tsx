import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import Card from '../common/Card'
import { formatNumber } from '../../utils/formatters'
import type { PropertyStats } from '../../types/property'

interface MarketTrendsProps {
  stats: PropertyStats
}

const COLORS = ['#0284c7', '#10b981', '#8b5cf6', '#f59e0b']

export default function MarketTrends({ stats }: MarketTrendsProps) {
  // Property type distribution
  const typeData = Object.entries(stats.by_property_type || {})
    .filter(([type]) => type)
    .map(([type, count]) => ({
      name: type.charAt(0).toUpperCase() + type.slice(1),
      count,
    }))
    .sort((a, b) => b.count - a.count)

  // Suburb distribution
  const suburbData = Object.entries(stats.by_suburb || {}).map(
    ([suburb, data]) => ({
      name: suburb,
      forSale: data.for_sale || 0,
      sold: data.sold || 0,
    })
  )

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card className="h-64">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          By Property Type
        </h3>
        <ResponsiveContainer width="100%" height="80%">
          <BarChart data={typeData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 12 }}
              width={80}
            />
            <Tooltip formatter={(value: number) => [formatNumber(value), 'Count']} />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {typeData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card className="h-64">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          By Suburb
        </h3>
        <ResponsiveContainer width="100%" height="80%">
          <BarChart data={suburbData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value: number) => formatNumber(value)} />
            <Bar dataKey="forSale" name="For Sale" fill="#0284c7" />
            <Bar dataKey="sold" name="Sold" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}
