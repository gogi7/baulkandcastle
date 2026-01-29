import { Home, CheckCircle, TrendingUp, Calendar } from 'lucide-react'
import Card from '../common/Card'
import { formatPrice, formatNumber } from '../../utils/formatters'
import type { PropertyStats } from '../../types/property'

interface StatsCardsProps {
  stats: PropertyStats
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'For Sale',
      value: formatNumber(stats.total_for_sale),
      subValue: formatPrice(stats.avg_price_for_sale, true) + ' avg',
      icon: Home,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Sold (All Time)',
      value: formatNumber(stats.total_sold),
      subValue: formatPrice(stats.avg_price_sold, true) + ' avg',
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'New This Week',
      value: formatNumber(stats.new_this_week),
      subValue: 'New listings',
      icon: TrendingUp,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      title: 'Sold This Week',
      value: formatNumber(stats.sold_this_week),
      subValue: 'Recent sales',
      icon: Calendar,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-gray-500">{card.title}</p>
              <p className="mt-1 text-2xl font-semibold text-gray-900">
                {card.value}
              </p>
              <p className="mt-1 text-sm text-gray-500">{card.subValue}</p>
            </div>
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <card.icon className={`w-5 h-5 ${card.color}`} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
