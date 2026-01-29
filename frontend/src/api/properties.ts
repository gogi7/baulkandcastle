import api from './client'
import type { Property, PropertyStats, TrendData, DataFreshness } from '../types/property'

interface PropertiesResponse {
  status: string
  count: number
  properties: Property[]
}

interface SoldResponse {
  status: string
  count: number
  total: number
  properties: Property[]
}

interface StatsResponse {
  status: string
  stats: PropertyStats
}

interface TrendsResponse {
  status: string
  trends: TrendData[]
}

interface SuburbsResponse {
  status: string
  suburbs: string[]
}

interface DataFreshnessResponse {
  status: string
  freshness: DataFreshness
}

export async function fetchProperties(extended?: boolean): Promise<Property[]> {
  const { data } = await api.get<PropertiesResponse>('/properties', {
    params: extended ? { extended: 'true' } : undefined,
  })
  return data.properties
}

export async function fetchProperty(id: string): Promise<{
  property: Property
  history: Array<{ date: string; price_display: string; price_value: number; status: string }>
  prediction: { predicted_price: number; price_range_low: number; price_range_high: number } | null
  estimate: { estimate_low: number; estimate_mid: number; estimate_high: number } | null
}> {
  const { data } = await api.get(`/properties/${id}`)
  return data
}

export async function fetchSoldProperties(params?: {
  limit?: number
  offset?: number
}): Promise<{ properties: Property[]; total: number }> {
  const { data } = await api.get<SoldResponse>('/sold', { params })
  return { properties: data.properties, total: data.total }
}

export async function fetchStats(): Promise<PropertyStats> {
  const { data } = await api.get<StatsResponse>('/stats')
  return data.stats
}

export async function fetchTrends(months?: number): Promise<TrendData[]> {
  const { data } = await api.get<TrendsResponse>('/stats/trends', {
    params: { months },
  })
  return data.trends
}

export async function fetchSuburbs(): Promise<string[]> {
  const { data } = await api.get<SuburbsResponse>('/suburbs')
  return data.suburbs
}

export async function fetchDataFreshness(): Promise<DataFreshness> {
  const { data } = await api.get<DataFreshnessResponse>('/data-freshness')
  return data.freshness
}
