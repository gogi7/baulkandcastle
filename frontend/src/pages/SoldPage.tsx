import { useState } from 'react'
import { useSoldProperties, useSuburbs } from '../hooks/useProperties'
import PropertyTable from '../components/properties/PropertyTable'
import Button from '../components/common/Button'
import Select from '../components/common/Select'
import Input from '../components/common/Input'
import Card from '../components/common/Card'
import { LoadingPage } from '../components/common/Loading'
import { formatNumber } from '../utils/formatters'
import type { PropertyFilters } from '../types/property'

const propertyTypes = [
  { value: '', label: 'All Types' },
  { value: 'house', label: 'House' },
  { value: 'unit', label: 'Unit' },
  { value: 'townhouse', label: 'Townhouse' },
  { value: 'apartment-unit-flat', label: 'Apartment' },
]

export default function SoldPage() {
  const [limit, setLimit] = useState(100)
  const [filters, setFilters] = useState<PropertyFilters>({})
  const { data: suburbs } = useSuburbs()
  const { data, isLoading } = useSoldProperties({ limit }, filters)

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

  const properties = data?.properties || []
  const total = data?.total || 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sold Properties</h1>
          <p className="text-gray-500">
            Showing {formatNumber(properties.length)} of {formatNumber(total)} sold properties
          </p>
        </div>
        {properties.length < total && (
          <Button
            variant="outline"
            onClick={() => setLimit((prev) => prev + 100)}
          >
            Load More
          </Button>
        )}
      </div>

      <Card>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
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
        </div>
      </Card>

      <PropertyTable data={properties} showSoldDate />
    </div>
  )
}
