import { useMemo, useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ExternalLink, ChevronUp, ChevronDown, TrendingUp, TrendingDown } from 'lucide-react'
import Card from '../common/Card'
import Button from '../common/Button'
import FreshnessBadge from '../common/FreshnessBadge'
import { formatPrice, formatDate, formatLandSize } from '../../utils/formatters'
import type { Property } from '../../types/property'

interface PropertyTableProps {
  data: Property[]
  showSoldDate?: boolean
  showExtended?: boolean
  onRowClick?: (property: Property) => void
}

export default function PropertyTable({ data, showSoldDate = false, showExtended = false, onRowClick }: PropertyTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')

  // Helper function to format price in compact form (e.g., $1.5M)
  const formatCompactPrice = (value: number | null | undefined): string => {
    if (value == null || value === 0) return '-'
    if (value >= 1000000) {
      return `$${(value / 1000000).toFixed(1)}M`
    }
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(0)}K`
    }
    return `$${value.toFixed(0)}`
  }

  // Helper function to format price range
  const formatPriceRange = (low: number | null | undefined, high: number | null | undefined): string => {
    if (low == null || high == null) return ''
    return `${formatCompactPrice(low)} - ${formatCompactPrice(high)}`
  }

  const columns = useMemo<ColumnDef<Property>[]>(
    () => [
      {
        accessorKey: 'address',
        header: 'Address',
        cell: ({ row }) => (
          <div className="min-w-[200px]">
            <p className="font-medium text-gray-900">{row.original.address}</p>
            <p className="text-xs text-gray-500">{row.original.suburb}</p>
          </div>
        ),
      },
      {
        accessorKey: 'price_value',
        header: 'Price',
        cell: ({ row }) => (
          <div className="text-right">
            <p className="font-semibold">{formatPrice(row.original.price_value)}</p>
            <p className="text-xs text-gray-500">{row.original.price_display}</p>
          </div>
        ),
      },
      {
        accessorKey: 'beds',
        header: 'Beds',
        cell: ({ getValue }) => <span className="text-center block">{getValue() as number}</span>,
      },
      {
        accessorKey: 'baths',
        header: 'Baths',
        cell: ({ getValue }) => <span className="text-center block">{getValue() as number}</span>,
      },
      {
        accessorKey: 'cars',
        header: 'Cars',
        cell: ({ getValue }) => <span className="text-center block">{getValue() as number}</span>,
      },
      {
        accessorKey: 'land_size',
        header: 'Land',
        cell: ({ getValue }) => formatLandSize(getValue() as string | null),
      },
      {
        accessorKey: 'property_type',
        header: 'Type',
        cell: ({ getValue }) => (
          <span className="capitalize">{(getValue() as string)?.replace(/-/g, ' ') || '-'}</span>
        ),
      },
      ...(showSoldDate
        ? [
            {
              accessorKey: 'sold_date',
              header: 'Sold Date',
              cell: ({ row }: { row: { original: Property } }) =>
                formatDate(row.original.sold_date_iso || row.original.sold_date),
            } as ColumnDef<Property>,
          ]
        : [
            {
              accessorKey: 'first_seen',
              header: 'Listed',
              cell: ({ getValue }: { getValue: () => unknown }) => formatDate(getValue() as string),
            } as ColumnDef<Property>,
          ]),
      // Extended columns - only shown when showExtended is true
      ...(showExtended
        ? [
            {
              id: 'domain_estimate',
              accessorKey: 'domain_estimate_mid',
              header: 'Domain Est.',
              cell: ({ row }: { row: { original: Property } }) => {
                const { domain_estimate_mid, domain_estimate_low, domain_estimate_high, domain_scraped_at } = row.original
                if (domain_estimate_mid == null) return <span className="text-gray-400">-</span>
                return (
                  <div className="text-right min-w-[100px]">
                    <p className="font-semibold text-blue-600">{formatCompactPrice(domain_estimate_mid)}</p>
                    <p className="text-xs text-gray-500">
                      {formatPriceRange(domain_estimate_low, domain_estimate_high)}
                    </p>
                    <FreshnessBadge date={domain_scraped_at} />
                  </div>
                )
              },
            } as ColumnDef<Property>,
            {
              id: 'xgboost_estimate',
              accessorKey: 'xgboost_predicted_price',
              header: 'XGBoost Est.',
              cell: ({ row }: { row: { original: Property } }) => {
                const { xgboost_predicted_price, xgboost_price_low, xgboost_price_high, xgboost_predicted_at } = row.original
                if (xgboost_predicted_price == null) return <span className="text-gray-400">-</span>
                return (
                  <div className="text-right min-w-[100px]">
                    <p className="font-semibold text-purple-600">{formatCompactPrice(xgboost_predicted_price)}</p>
                    <p className="text-xs text-gray-500">
                      {formatPriceRange(xgboost_price_low, xgboost_price_high)}
                    </p>
                    <FreshnessBadge date={xgboost_predicted_at} />
                  </div>
                )
              },
            } as ColumnDef<Property>,
            {
              id: 'changes',
              accessorKey: 'days_on_market',
              header: 'Changes',
              cell: ({ row }: { row: { original: Property } }) => {
                const { days_on_market, initial_price, price_value, price_change_count } = row.original
                const priceChange = initial_price && price_value ? price_value - initial_price : null
                const changeCount = price_change_count != null && price_change_count > 1 ? price_change_count - 1 : 0

                return (
                  <div className="min-w-[100px]">
                    <p className="text-sm text-gray-700">
                      {days_on_market != null ? `${days_on_market}d` : '-'}
                      {changeCount > 0 && (
                        <span className="text-gray-400"> | {changeCount} {changeCount === 1 ? 'change' : 'changes'}</span>
                      )}
                    </p>
                    {priceChange != null && priceChange !== 0 && (
                      <div className={`flex items-center text-xs ${priceChange < 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {priceChange < 0 ? (
                          <TrendingDown className="w-3 h-3 mr-1" />
                        ) : (
                          <TrendingUp className="w-3 h-3 mr-1" />
                        )}
                        {formatCompactPrice(Math.abs(priceChange))}
                      </div>
                    )}
                  </div>
                )
              },
            } as ColumnDef<Property>,
          ]
        : []),
      {
        id: 'actions',
        header: '',
        cell: ({ row }) =>
          row.original.url && (
            <a
              href={row.original.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-primary-600"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          ),
      },
    ],
    [showSoldDate, showExtended]
  )

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
  })

  return (
    <Card padding="none">
      <div className="p-4 border-b border-gray-200">
        <input
          type="text"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder="Search properties..."
          className="w-full max-w-sm px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center space-x-1">
                      <span>
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                      </span>
                      {header.column.getIsSorted() === 'asc' && (
                        <ChevronUp className="w-4 h-4" />
                      )}
                      {header.column.getIsSorted() === 'desc' && (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className={`hover:bg-gray-50 ${onRowClick ? 'cursor-pointer' : ''}`}
                onClick={() => onRowClick?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3 text-sm text-gray-900">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
        <div className="text-sm text-gray-500">
          Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}{' '}
          to{' '}
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            table.getFilteredRowModel().rows.length
          )}{' '}
          of {table.getFilteredRowModel().rows.length}
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </Card>
  )
}
