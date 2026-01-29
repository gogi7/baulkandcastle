import { useState } from 'react'
import Button from '../common/Button'
import Input from '../common/Input'
import Select from '../common/Select'
import Card from '../common/Card'
import type { PredictionInput } from '../../types/prediction'

interface PredictorFormProps {
  onSubmit: (input: PredictionInput) => void
  isLoading: boolean
}

const propertyTypes = [
  { value: 'house', label: 'House' },
  { value: 'unit', label: 'Unit / Apartment' },
  { value: 'townhouse', label: 'Townhouse' },
  { value: 'other', label: 'Other' },
]

const suburbs = [
  { value: 'CASTLE HILL', label: 'Castle Hill' },
  { value: 'BAULKHAM HILLS', label: 'Baulkham Hills' },
]

export default function PredictorForm({ onSubmit, isLoading }: PredictorFormProps) {
  const [formData, setFormData] = useState<PredictionInput>({
    beds: 4,
    bathrooms: 2,
    car_spaces: 2,
    land_size: undefined,
    suburb: 'CASTLE HILL',
    property_type: 'house',
  })

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]:
        name === 'land_size'
          ? value ? Number(value) : undefined
          : ['beds', 'bathrooms', 'car_spaces'].includes(name)
          ? Number(value)
          : value,
    }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Property Details
      </h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Select
            label="Property Type"
            name="property_type"
            value={formData.property_type}
            onChange={handleChange}
            options={propertyTypes}
          />
          <Select
            label="Suburb"
            name="suburb"
            value={formData.suburb}
            onChange={handleChange}
            options={suburbs}
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <Input
            label="Bedrooms"
            name="beds"
            type="number"
            min={1}
            max={10}
            value={formData.beds}
            onChange={handleChange}
          />
          <Input
            label="Bathrooms"
            name="bathrooms"
            type="number"
            min={1}
            max={10}
            value={formData.bathrooms}
            onChange={handleChange}
          />
          <Input
            label="Car Spaces"
            name="car_spaces"
            type="number"
            min={0}
            max={10}
            value={formData.car_spaces}
            onChange={handleChange}
          />
        </div>

        <Input
          label="Land Size (m²)"
          name="land_size"
          type="number"
          min={0}
          max={10000}
          value={formData.land_size || ''}
          onChange={handleChange}
          placeholder="Optional for units"
        />

        <Button type="submit" loading={isLoading} className="w-full">
          Get Valuation
        </Button>
      </form>
    </Card>
  )
}
