import { Home, Activity } from 'lucide-react'
import { useHealth } from '../../hooks/usePrediction'

export default function Header() {
  const { data: health } = useHealth()

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-white border-b border-gray-200 z-50">
      <div className="flex items-center justify-between h-full px-6">
        <div className="flex items-center space-x-3">
          <Home className="w-8 h-8 text-primary-600" />
          <div>
            <h1 className="text-lg font-semibold text-gray-900">
              Property Tracker
            </h1>
            <p className="text-xs text-gray-500">
              Baulkham Hills & Castle Hill
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {health && (
            <div className="flex items-center space-x-2">
              <Activity
                className={`w-4 h-4 ${
                  health.status === 'healthy'
                    ? 'text-green-500'
                    : 'text-red-500'
                }`}
              />
              <span className="text-sm text-gray-600">
                {health.status === 'healthy' ? 'Model Ready' : 'Model Unavailable'}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
