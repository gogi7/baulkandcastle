import type { ToolFlag } from '../../types/tools'
import Input from '../common/Input'
import Select from '../common/Select'

interface ToolFlagFormProps {
  flags: ToolFlag[]
  values: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
}

export default function ToolFlagForm({ flags, values, onChange }: ToolFlagFormProps) {
  return (
    <div className="space-y-3">
      {flags.map((flag) => {
        const value = values[flag.name] ?? flag.default

        if (flag.type === 'boolean') {
          return (
            <label key={flag.name} className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={Boolean(value)}
                onChange={(e) => onChange(flag.name, e.target.checked)}
                className="mt-0.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">{flag.name}</span>
                <p className="text-xs text-gray-500">{flag.description}</p>
              </div>
            </label>
          )
        }

        if (flag.type === 'select' && flag.options) {
          return (
            <Select
              key={flag.name}
              label={flag.name}
              value={String(value || '')}
              onChange={(e) => onChange(flag.name, e.target.value)}
              options={flag.options.map((opt) => ({
                value: opt,
                label: opt === '' ? '(All)' : opt,
              }))}
            />
          )
        }

        if (flag.type === 'number') {
          return (
            <Input
              key={flag.name}
              label={flag.name}
              type="number"
              value={value !== null && value !== undefined ? String(value) : ''}
              onChange={(e) =>
                onChange(flag.name, e.target.value ? Number(e.target.value) : null)
              }
              placeholder={flag.description}
            />
          )
        }

        // string type
        return (
          <Input
            key={flag.name}
            label={flag.name}
            type="text"
            value={String(value || '')}
            onChange={(e) => onChange(flag.name, e.target.value || null)}
            placeholder={flag.description}
          />
        )
      })}
    </div>
  )
}
