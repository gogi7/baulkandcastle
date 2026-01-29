import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import Card from '../common/Card'
import { formatPrice } from '../../utils/formatters'
import type { TrendData } from '../../types/property'

interface PriceChartProps {
  trends: TrendData[]
}

export default function PriceChart({ trends }: PriceChartProps) {
  // Group by month and calculate average
  const monthlyData = trends.reduce((acc, item) => {
    const existing = acc.find((d) => d.month === item.month)
    if (existing) {
      existing.totalPrice += item.avg_price * item.count
      existing.count += item.count
    } else {
      acc.push({
        month: item.month,
        totalPrice: item.avg_price * item.count,
        count: item.count,
      })
    }
    return acc
  }, [] as Array<{ month: string; totalPrice: number; count: number }>)

  const chartData = monthlyData
    .map((d) => ({
      month: d.month,
      avgPrice: Math.round(d.totalPrice / d.count),
      sales: d.count,
    }))
    .sort((a, b) => a.month.localeCompare(b.month))

  return (
    <Card className="h-80">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Price Trends
      </h3>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => {
              const [year, month] = value.split('-')
              return `${month}/${year.slice(2)}`
            }}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => formatPrice(value, true)}
          />
          <Tooltip
            formatter={(value: number, name: string) => [
              name === 'avgPrice' ? formatPrice(value) : value,
              name === 'avgPrice' ? 'Avg Price' : 'Sales',
            ]}
            labelFormatter={(label) => `Month: ${label}`}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="avgPrice"
            name="Avg Price"
            stroke="#0284c7"
            strokeWidth={2}
            dot={{ fill: '#0284c7', strokeWidth: 0, r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}
