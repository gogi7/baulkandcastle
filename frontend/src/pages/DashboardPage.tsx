import { useState, useMemo } from 'react'
import { useStats, useProperties, useSoldProperties, useSuburbs } from '../hooks/useProperties'
import StatsCards from '../components/dashboard/StatsCards'
import PriceChart from '../components/dashboard/PriceChart'
import RecentListings from '../components/dashboard/RecentListings'
import MarketTrends from '../components/dashboard/MarketTrends'
import { LoadingPage } from '../components/common/Loading'
import Select from '../components/common/Select'
import Input from '../components/common/Input'
import Card from '../components/common/Card'
import type { PropertyFilters, PropertyStats, TrendData } from '../types/property'

const propertyTypes = [
  { value: '', label: 'All Types' },
  { value: 'house', label: 'House' },
  { value: 'unit', label: 'Unit' },
  { value: 'townhouse', label: 'Townhouse' },
  { value: 'apartment-unit-flat', label: 'Apartment' },
]

export default function DashboardPage() {
  const [filters, setFilters] = useState<PropertyFilters>({})
  const { data: stats, isLoading: statsLoading } = useStats()
  const { data: allProperties, isLoading: propertiesLoading } = useProperties()
  const { data: filteredProperties } = useProperties(filters)
  const { data: soldData, isLoading: soldLoading } = useSoldProperties({ limit: 5000 }, filters)
  const { data: suburbs } = useSuburbs()

  const suburbOptions = [
    { value: '', label: 'All Suburbs' },
    ...(suburbs?.map((s) => ({ value: s, label: s })) || []),
  ]

  const handleFilterChange = (key: keyof PropertyFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
    }))
  }

  const handleNumberFilterChange = (key: keyof PropertyFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value ? Number(value) : undefined,
    }))
  }

  const hasActiveFilters = Object.values(filters).some((v) => v !== undefined)

  // Compute price trends from filtered sold properties
  const filteredTrends = useMemo((): TrendData[] => {
    if (!soldData?.properties) return []

    const soldProperties = soldData.properties.filter((p) => p.sold_date_iso)

    // Group by month
    const monthlyData: Record<string, { totalPrice: number; count: number; suburb: string; property_type: string }> = {}

    soldProperties.forEach((property) => {
      if (!property.sold_date_iso || !property.price_value) return
      const month = property.sold_date_iso.substring(0, 7) // YYYY-MM format

      if (!monthlyData[month]) {
        monthlyData[month] = {
          totalPrice: 0,
          count: 0,
          suburb: property.suburb || '',
          property_type: property.property_type || '',
        }
      }
      monthlyData[month].totalPrice += property.price_value
      monthlyData[month].count += 1
    })

    // Convert to TrendData format - show all historical data from earliest sold
    return Object.entries(monthlyData)
      .map(([month, data]) => ({
        month,
        suburb: data.suburb,
        property_type: data.property_type,
        count: data.count,
        avg_price: Math.round(data.totalPrice / data.count),
        avg_price_per_m2: 0,
      }))
      .sort((a, b) => a.month.localeCompare(b.month))
  }, [soldData?.properties])

  // Compute stats from filtered properties when filters are active
  const filteredStats = useMemo((): PropertyStats | undefined => {
    if (!stats) return stats
    if (!hasActiveFilters) return stats
    if (!filteredProperties || !allProperties) return stats

    const soldProperties = soldData?.properties || []

    const oneWeekAgo = new Date()
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)

    const newThisWeek = filteredProperties.filter((p) => {
      if (!p.first_seen) return false
      return new Date(p.first_seen) >= oneWeekAgo
    }).length

    const soldThisWeek = soldProperties.filter((p) => {
      if (!p.sold_date_iso) return false
      return new Date(p.sold_date_iso) >= oneWeekAgo
    }).length

    const totalPrice = filteredProperties.reduce((sum, p) => sum + (p.price_value || 0), 0)
    const avgPrice = filteredProperties.length > 0 ? totalPrice / filteredProperties.length : 0

    const totalSoldPrice = soldProperties.reduce((sum, p) => sum + (p.price_value || 0), 0)
    const avgSoldPrice = soldProperties.length > 0 ? totalSoldPrice / soldProperties.length : 0

    // Build by_property_type from filtered data
    const byPropertyType: Record<string, number> = {}
    filteredProperties.forEach((p) => {
      if (p.property_type) {
        byPropertyType[p.property_type] = (byPropertyType[p.property_type] || 0) + 1
      }
    })

    // Build by_suburb from filtered data (including sold)
    const bySuburb: Record<string, { for_sale: number; sold: number }> = {}
    filteredProperties.forEach((p) => {
      if (p.suburb) {
        if (!bySuburb[p.suburb]) {
          bySuburb[p.suburb] = { for_sale: 0, sold: 0 }
        }
        bySuburb[p.suburb].for_sale += 1
      }
    })
    soldProperties.forEach((p) => {
      if (p.suburb) {
        if (!bySuburb[p.suburb]) {
          bySuburb[p.suburb] = { for_sale: 0, sold: 0 }
        }
        bySuburb[p.suburb].sold += 1
      }
    })

    return {
      total_for_sale: filteredProperties.length,
      total_sold: soldProperties.length,
      new_this_week: newThisWeek,
      sold_this_week: soldThisWeek,
      avg_price_for_sale: avgPrice,
      avg_price_sold: avgSoldPrice,
      by_suburb: bySuburb,
      by_property_type: byPropertyType,
    }
  }, [filteredProperties, allProperties, soldData?.properties, stats, hasActiveFilters])

  if (statsLoading || propertiesLoading || soldLoading) {
    return <LoadingPage />
  }

  const displayStats = filteredStats || stats
  const displayProperties = filteredProperties || allProperties
  const displayTrends = filteredTrends

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">
          Property market overview for Baulkham Hills & Castle Hill
        </p>
      </div>

      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <Select
            label="Suburb"
            options={suburbOptions}
            value={filters.suburb || ''}
            onChange={(e) => handleFilterChange('suburb', e.target.value)}
          />
          <Select
            label="Property Type"
            options={propertyTypes}
            value={filters.property_type || ''}
            onChange={(e) => handleFilterChange('property_type', e.target.value)}
          />
          <Input
            label="Bedrooms"
            type="number"
            min={1}
            max={10}
            placeholder="Any"
            value={filters.beds || ''}
            onChange={(e) => handleNumberFilterChange('beds', e.target.value)}
          />
          <Input
            label="Bathrooms"
            type="number"
            min={1}
            max={10}
            placeholder="Any"
            value={filters.baths || ''}
            onChange={(e) => handleNumberFilterChange('baths', e.target.value)}
          />
          <Input
            label="Min Land (m²)"
            type="number"
            min={0}
            placeholder="Any"
            value={filters.min_land_size || ''}
            onChange={(e) => handleNumberFilterChange('min_land_size', e.target.value)}
          />
          <div className="flex items-end col-span-2 lg:col-span-2">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={filters.excelsior_only || false}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    excelsior_only: e.target.checked || undefined,
                  }))
                }
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700">Excelsior Catchment</span>
            </label>
          </div>
        </div>
      </Card>

      {displayStats && <StatsCards stats={displayStats} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {displayTrends && displayTrends.length > 0 && <PriceChart trends={displayTrends} />}
        </div>
        <div>
          {displayProperties && <RecentListings properties={displayProperties} />}
        </div>
      </div>

      {displayStats && <MarketTrends stats={displayStats} />}
    </div>
  )
}
