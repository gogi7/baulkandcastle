/**
 * Format a price value as a currency string
 */
export function formatPrice(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined) return '-'

  if (compact) {
    if (value >= 1_000_000) {
      const millions = value / 1_000_000
      return `$${millions % 1 === 0 ? millions.toFixed(0) : millions.toFixed(1)}M`
    }
    if (value >= 1_000) {
      const thousands = value / 1_000
      return `$${thousands % 1 === 0 ? thousands.toFixed(0) : thousands.toFixed(0)}K`
    }
  }

  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: 0,
  }).format(value)
}

/**
 * Format a price range
 */
export function formatPriceRange(low: number, high: number, compact = false): string {
  if (low === high) return formatPrice(low, compact)
  return `${formatPrice(low, compact)} - ${formatPrice(high, compact)}`
}

/**
 * Format a date string
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'

  try {
    const date = new Date(dateStr)
    return new Intl.DateTimeFormat('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date)
  } catch {
    return dateStr
  }
}

/**
 * Format a relative date (e.g., "2 days ago")
 */
export function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'

  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMinutes < 1) return 'just now'
    if (diffMinutes < 60) return `${diffMinutes}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
    return `${Math.floor(diffDays / 365)} years ago`
  } catch {
    return dateStr
  }
}

/**
 * Format a number with thousands separators
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-AU').format(value)
}

/**
 * Format a percentage
 */
export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(decimals)}%`
}

/**
 * Format land size
 */
export function formatLandSize(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  return `${formatNumber(value)}m²`
}

/**
 * Capitalize first letter
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

/**
 * Format property type for display
 */
export function formatPropertyType(type: string | null | undefined): string {
  if (!type) return 'Unknown'
  return type
    .split('-')
    .map(capitalize)
    .join(' ')
}

/**
 * Calculate freshness age in days from a date string
 */
export function getFreshnessAgeDays(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null

  try {
    const date = new Date(dateStr)
    const now = new Date()
    return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  } catch {
    return null
  }
}

/**
 * Format freshness age for display (e.g., "2d", "1w", "3mo")
 */
export function formatFreshnessAge(dateStr: string | null | undefined): string {
  const days = getFreshnessAgeDays(dateStr)
  if (days === null) return '-'

  if (days === 0) return 'today'
  if (days === 1) return '1d'
  if (days < 7) return `${days}d`
  if (days < 30) return `${Math.floor(days / 7)}w`
  if (days < 365) return `${Math.floor(days / 30)}mo`
  return `${Math.floor(days / 365)}y`
}

/**
 * Get freshness color classes based on age
 * Green: < 7 days, Amber: 7-30 days, Gray: > 30 days
 */
export function getFreshnessColorClasses(dateStr: string | null | undefined): string {
  const days = getFreshnessAgeDays(dateStr)
  if (days === null) return 'text-gray-400 bg-gray-50'

  if (days < 7) return 'text-green-600 bg-green-50'
  if (days <= 30) return 'text-amber-600 bg-amber-50'
  return 'text-gray-500 bg-gray-100'
}
