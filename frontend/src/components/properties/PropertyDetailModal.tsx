import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, ExternalLink, Home, TrendingUp, TrendingDown } from 'lucide-react'
import { fetchProperty } from '../../api/properties'
import Card from '../common/Card'
import Button from '../common/Button'
import FreshnessBadge from '../common/FreshnessBadge'
import { formatPrice, formatDate, formatPropertyType } from '../../utils/formatters'
import type { Property } from '../../types/property'

interface PropertyDetailModalProps {
  property: Property
  onClose: () => void
}

export default function PropertyDetailModal({ property, onClose }: PropertyDetailModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['property', property.property_id],
    queryFn: () => fetchProperty(property.property_id),
  })

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])

  const history = data?.history || []
  const prediction = data?.prediction
  const estimate = data?.estimate

  // Calculate price changes from history
  const priceHistory = history
    .filter((h) => h.status === 'sale' && h.price_value > 0)
    .map((h, idx, arr) => ({
      ...h,
      change: idx > 0 ? h.price_value - arr[idx - 1].price_value : null,
    }))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div
        ref={modalRef}
        className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Home className="w-5 h-5 text-gray-400 flex-shrink-0" />
              <h2 className="text-lg font-semibold text-gray-900 truncate">
                {property.address}
              </h2>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {property.suburb} | {formatPropertyType(property.property_type)}
            </p>
            <div className="flex gap-4 mt-2 text-sm text-gray-600">
              <span>{property.beds} bed</span>
              <span>{property.baths} bath</span>
              <span>{property.cars} car</span>
              {property.land_size && <span>{property.land_size}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {property.url && (
              <a
                href={property.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-gray-400 hover:text-primary-600 rounded-lg hover:bg-gray-100"
              >
                <ExternalLink className="w-5 h-5" />
              </a>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            </div>
          ) : (
            <>
              {/* Estimates Comparison */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Estimate Comparison</h3>
                <div className="grid grid-cols-3 gap-3">
                  <Card className="text-center">
                    <p className="text-xs text-gray-500 mb-1">Listed Price</p>
                    <p className="text-lg font-bold text-gray-900">
                      {formatPrice(property.price_value)}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {property.price_display}
                    </p>
                  </Card>
                  <Card className="text-center">
                    <p className="text-xs text-gray-500 mb-1">Domain Estimate</p>
                    {estimate ? (
                      <>
                        <p className="text-lg font-bold text-blue-600">
                          {formatPrice(estimate.estimate_mid)}
                        </p>
                        <p className="text-xs text-gray-400">
                          {formatPrice(estimate.estimate_low)} - {formatPrice(estimate.estimate_high)}
                        </p>
                        <div className="mt-1">
                          <FreshnessBadge date={property.domain_scraped_at} />
                        </div>
                      </>
                    ) : (
                      <p className="text-lg text-gray-400">-</p>
                    )}
                  </Card>
                  <Card className="text-center">
                    <p className="text-xs text-gray-500 mb-1">XGBoost Estimate</p>
                    {prediction ? (
                      <>
                        <p className="text-lg font-bold text-purple-600">
                          {formatPrice(prediction.predicted_price)}
                        </p>
                        <p className="text-xs text-gray-400">
                          {formatPrice(prediction.price_range_low)} - {formatPrice(prediction.price_range_high)}
                        </p>
                        <div className="mt-1">
                          <FreshnessBadge date={property.xgboost_predicted_at} />
                        </div>
                      </>
                    ) : (
                      <p className="text-lg text-gray-400">-</p>
                    )}
                  </Card>
                </div>
              </div>

              {/* Price History Timeline */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Price History</h3>
                {priceHistory.length > 0 ? (
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Date
                          </th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                            Price
                          </th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                            Change
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {priceHistory.map((entry, idx) => (
                          <tr key={idx}>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {formatDate(entry.date)}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900 text-right">
                              {entry.price_display || formatPrice(entry.price_value)}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {entry.change !== null && entry.change !== 0 ? (
                                <span
                                  className={`inline-flex items-center text-xs ${
                                    entry.change < 0 ? 'text-green-600' : 'text-red-600'
                                  }`}
                                >
                                  {entry.change < 0 ? (
                                    <TrendingDown className="w-3 h-3 mr-1" />
                                  ) : (
                                    <TrendingUp className="w-3 h-3 mr-1" />
                                  )}
                                  {formatPrice(Math.abs(entry.change))}
                                </span>
                              ) : (
                                <span className="text-xs text-gray-400">-</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-4">
                    No price history available
                  </p>
                )}
              </div>

              {/* Listing Info */}
              <div className="text-sm text-gray-500 space-y-1">
                <p>
                  <span className="font-medium">First seen:</span>{' '}
                  {formatDate(property.first_seen)}
                </p>
                {property.days_on_market != null && (
                  <p>
                    <span className="font-medium">Days on market:</span>{' '}
                    {property.days_on_market}
                  </p>
                )}
                {property.agent && (
                  <p>
                    <span className="font-medium">Agent:</span> {property.agent}
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
