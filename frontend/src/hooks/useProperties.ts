import { useQuery } from '@tanstack/react-query'
import { fetchProperties, fetchSoldProperties, fetchStats, fetchTrends, fetchSuburbs, fetchDataFreshness } from '../api/properties'
import type { PropertyFilters } from '../types/property'

export function useProperties(filters?: PropertyFilters, extended?: boolean) {
  return useQuery({
    queryKey: ['properties', filters, extended],
    queryFn: () => fetchProperties(extended),
    select: (data) => {
      if (!filters) return data

      return data.filter((property) => {
        if (filters.suburb && property.suburb !== filters.suburb) return false
        if (filters.property_type && property.property_type !== filters.property_type) return false
        if (filters.min_price && property.price_value < filters.min_price) return false
        if (filters.max_price && property.price_value > filters.max_price) return false
        if (filters.beds && property.beds !== filters.beds) return false
        if (filters.baths && property.baths !== filters.baths) return false
        if (filters.min_land_size) {
          const landSize = property.land_size ? parseFloat(property.land_size.replace(/[^0-9.]/g, '')) : 0
          if (landSize < filters.min_land_size) return false
        }
        if (filters.excelsior_only && !property.in_excelsior_catchment) return false
        return true
      })
    },
  })
}

export function useSoldProperties(params?: { limit?: number; offset?: number }, filters?: PropertyFilters) {
  return useQuery({
    queryKey: ['sold', params, filters],
    queryFn: () => fetchSoldProperties(params),
    select: (data) => {
      if (!filters) return data

      const filteredProperties = data.properties.filter((property) => {
        if (filters.suburb && property.suburb !== filters.suburb) return false
        if (filters.property_type && property.property_type !== filters.property_type) return false
        if (filters.min_price && property.price_value < filters.min_price) return false
        if (filters.max_price && property.price_value > filters.max_price) return false
        if (filters.beds && property.beds !== filters.beds) return false
        if (filters.baths && property.baths !== filters.baths) return false
        if (filters.min_land_size) {
          const landSize = property.land_size ? parseFloat(property.land_size.replace(/[^0-9.]/g, '')) : 0
          if (landSize < filters.min_land_size) return false
        }
        if (filters.excelsior_only && !property.in_excelsior_catchment) return false
        return true
      })

      return { properties: filteredProperties, total: data.total }
    },
  })
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
  })
}

export function useTrends(months?: number) {
  return useQuery({
    queryKey: ['trends', months],
    queryFn: () => fetchTrends(months),
  })
}

export function useSuburbs() {
  return useQuery({
    queryKey: ['suburbs'],
    queryFn: fetchSuburbs,
  })
}

export function useDataFreshness() {
  return useQuery({
    queryKey: ['data-freshness'],
    queryFn: fetchDataFreshness,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
