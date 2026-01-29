import { ExternalLink } from 'lucide-react'
import Card from '../common/Card'
import { formatPrice, formatRelativeDate } from '../../utils/formatters'
import type { Property } from '../../types/property'

interface RecentListingsProps {
  properties: Property[]
}

export default function RecentListings({ properties }: RecentListingsProps) {
  const recent = properties
    .sort((a, b) => (b.first_seen || '').localeCompare(a.first_seen || ''))
    .slice(0, 5)

  return (
    <Card padding="none">
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          Recent Listings
        </h3>
      </div>
      <ul className="divide-y divide-gray-200">
        {recent.map((property) => (
          <li key={property.property_id} className="px-4 py-3">
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {property.address}
                </p>
                <p className="text-xs text-gray-500">
                  {property.suburb} · {property.beds} bed · {property.baths} bath
                  {property.land_size && ` · ${property.land_size}`}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  <span className="capitalize">{property.property_type?.replace(/-/g, ' ')}</span>
                  {' · '}
                  {formatRelativeDate(property.first_seen)}
                </p>
              </div>
              <div className="ml-4 flex items-center space-x-2">
                <span className="text-sm font-semibold text-gray-900">
                  {formatPrice(property.price_value, true)}
                </span>
                {property.url && (
                  <a
                    href={property.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-primary-600"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>
          </li>
        ))}
        {recent.length === 0 && (
          <li className="px-4 py-8 text-center text-gray-500">
            No recent listings
          </li>
        )}
      </ul>
    </Card>
  )
}
