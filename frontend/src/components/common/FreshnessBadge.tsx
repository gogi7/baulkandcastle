import clsx from 'clsx'
import { formatFreshnessAge, getFreshnessColorClasses } from '../../utils/formatters'

interface FreshnessBadgeProps {
  date: string | null | undefined
  label?: string
  className?: string
}

export default function FreshnessBadge({ date, label, className }: FreshnessBadgeProps) {
  const ageText = formatFreshnessAge(date)
  const colorClasses = getFreshnessColorClasses(date)

  if (ageText === '-') return null

  return (
    <span
      className={clsx(
        'inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium',
        colorClasses,
        className
      )}
    >
      {ageText}
      {label && <span className="ml-0.5 opacity-75">{label}</span>}
    </span>
  )
}
