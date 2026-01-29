import { useState } from 'react'
import { Clock } from 'lucide-react'
import { useProperties, useSuburbs, useDataFreshness } from '../hooks/useProperties'
import PropertyTable from '../components/properties/PropertyTable'
import PropertyDetailModal from '../components/properties/PropertyDetailModal'
import Select from '../components/common/Select'
import Input from '../components/common/Input'
import Card from '../components/common/Card'
import { LoadingPage } from '../components/common/Loading'
import { formatNumber, formatRelativeDate } from '../utils/formatters'
import type { Property, PropertyFilters } from '../types/property'

const propertyTypes = [
  { value: '', label: 'All Types' },
  { value: 'house', label: 'House' },
  { value: 'unit', label: 'Unit' },
  { value: 'townhouse', label: 'Townhouse' },
  { value: 'apartment-unit-flat', label: 'Apartment' },
]

export default function PropertiesPage() {
  const [filters, setFilters] = useState<PropertyFilters>({})
  const [showExtended, setShowExtended] = useState(false)
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null)
  const { data: suburbs } = useSuburbs()
  const { data: properties, isLoading } = useProperties(filters, showExtended)
  const { data: freshness } = useDataFreshness()

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

  if (isLoading) {
    return <LoadingPage />
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Properties For Sale</h1>
        <p className="text-gray-500">
          {formatNumber(properties?.length || 0)} properties currently listed
        </p>
        {freshness?.listing_last_scraped && (
          <div className="flex items-center gap-1.5 mt-1 text-sm text-gray-400">
            <Clock className="w-3.5 h-3.5" />
            <span>Listing data updated {formatRelativeDate(freshness.listing_last_scraped)}</span>
          </div>
        )}
      </div>

      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
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
          <div className="flex items-end">
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
          <div className="flex items-end">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={showExtended}
                onChange={(e) => setShowExtended(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700">Show Estimates</span>
            </label>
          </div>
        </div>
      </Card>

      {properties && (
        <PropertyTable
          data={properties}
          showExtended={showExtended}
          onRowClick={setSelectedProperty}
        />
      )}

      {selectedProperty && (
        <PropertyDetailModal
          property={selectedProperty}
          onClose={() => setSelectedProperty(null)}
        />
      )}
    </div>
  )
}
