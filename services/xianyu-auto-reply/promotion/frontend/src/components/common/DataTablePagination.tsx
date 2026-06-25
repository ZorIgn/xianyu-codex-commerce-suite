/**
 * 推广返佣系统 - 通用表格分页组件
 *
 * 功能：
 * 1. 统一表格分页底部样式
 * 2. 支持每页条数切换
 * 3. 支持上一页、下一页翻页
 * 4. 适配亮色和暗黑主题
 */
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface DataTablePaginationProps {
  total: number
  page: number
  totalPages: number
  pageSize: number
  loading?: boolean
  pageSizeOptions?: number[]
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

const DEFAULT_PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

/**
 * 渲染统一的表格分页区域。
 */
export function DataTablePagination({
  total,
  page,
  totalPages,
  pageSize,
  loading = false,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  onPageChange,
  onPageSizeChange,
}: DataTablePaginationProps) {
  if (total <= 0) {
    return null
  }

  const safeTotalPages = Math.max(totalPages || 0, 1)
  const safePage = Math.min(Math.max(page || 1, 1), safeTotalPages)
  const isPrevDisabled = loading || safePage <= 1
  const isNextDisabled = loading || safePage >= safeTotalPages

  return (
    <div className="flex-shrink-0 flex flex-col gap-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          共 {total} 条记录
        </span>
        <label className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <span>每页</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            disabled={loading}
            className="min-w-[88px] bg-transparent text-sm text-slate-700 outline-none focus:text-blue-600 disabled:cursor-not-allowed dark:text-slate-200"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size} 条
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-300">
          第 <span className="mx-1 font-semibold text-slate-900 dark:text-slate-100">{safePage}</span> / {safeTotalPages} 页
        </span>
        <button
          type="button"
          onClick={() => onPageChange(safePage - 1)}
          disabled={isPrevDisabled}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-slate-100"
          aria-label="上一页"
          title="上一页"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(safePage + 1)}
          disabled={isNextDisabled}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-slate-100"
          aria-label="下一页"
          title="下一页"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
