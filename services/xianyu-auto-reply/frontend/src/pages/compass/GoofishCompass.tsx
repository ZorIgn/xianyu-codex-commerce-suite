import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, ExternalLink, Filter, RefreshCw, TrendingUp } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { PageLoading } from '@/components/common/Loading'
import { Select } from '@/components/common/Select'
import {
  listGoofishCrawlItems,
  listGoofishCrawlJobs,
  type GoofishCrawlItem,
  type GoofishCrawlJob,
} from '@/api/goofishCrawler'

type SortKey = 'want_desc' | 'view_desc' | 'price_asc' | 'price_desc'

function parsePriceToNumber(price?: string): number | null {
  if (!price) return null
  const m = price.replace(/[,，]/g, '').match(/(\d+(?:\.\d+)?)/)
  if (!m) return null
  const n = Number(m[1])
  return Number.isFinite(n) ? n : null
}

function topN(items: GoofishCrawlItem[], key: 'want_count' | 'view_count', n: number) {
  return [...items]
    .sort((a, b) => (Number(b[key] || 0) - Number(a[key] || 0)))
    .slice(0, n)
}

function formatDateTime(value?: string | Date | null) {
  if (!value) return '-'
  const date = typeof value === 'string' ? new Date(value) : value
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString()
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType
  label: string
  value: string
}) {
  return (
    <div className="vben-card">
      <div className="vben-card-body flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
          <Icon className="w-5 h-5 text-slate-700 dark:text-slate-200" />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
          <div className="text-lg font-semibold text-slate-900 dark:text-slate-100 truncate">{value}</div>
        </div>
      </div>
    </div>
  )
}

export function GoofishCompass() {
  const { addToast } = useUIStore()

  const [loadingPage, setLoadingPage] = useState(true)
  const [sortKey, setSortKey] = useState<SortKey>('want_desc')

  const [crawlerJobs, setCrawlerJobs] = useState<GoofishCrawlJob[]>([])
  const [selectedCrawlerJobId, setSelectedCrawlerJobId] = useState<number | undefined>(undefined)
  const [crawlerItems, setCrawlerItems] = useState<GoofishCrawlItem[]>([])
  const [loadingCrawlerJobs, setLoadingCrawlerJobs] = useState(false)
  const [loadingCrawlerItems, setLoadingCrawlerItems] = useState(false)

  const loadCrawlerJobs = async (opts?: { keepSelection?: boolean }) => {
    try {
      setLoadingCrawlerJobs(true)
      const res = await listGoofishCrawlJobs()
      const jobs = res.jobs || []
      setCrawlerJobs(jobs)
      if (!opts?.keepSelection) {
        if (jobs.length > 0) setSelectedCrawlerJobId(jobs[0].id)
        else setSelectedCrawlerJobId(undefined)
      }
    } catch {
      addToast({ type: 'error', message: '加载定时任务失败' })
    } finally {
      setLoadingCrawlerJobs(false)
      setLoadingPage(false)
    }
  }

  useEffect(() => {
    loadCrawlerJobs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sortedItems = useMemo(() => {
    const list = [...crawlerItems]
    if (sortKey === 'want_desc') list.sort((a, b) => Number(b.want_count || 0) - Number(a.want_count || 0))
    if (sortKey === 'view_desc') list.sort((a, b) => Number(b.view_count || 0) - Number(a.view_count || 0))
    if (sortKey === 'price_asc') list.sort((a, b) => Number(parsePriceToNumber(a.price) || 0) - Number(parsePriceToNumber(b.price) || 0))
    if (sortKey === 'price_desc') list.sort((a, b) => Number(parsePriceToNumber(b.price) || 0) - Number(parsePriceToNumber(a.price) || 0))
    return list
  }, [crawlerItems, sortKey])

  const stats = useMemo(() => {
    const prices = crawlerItems.map((x) => parsePriceToNumber(x.price)).filter((x): x is number => x !== null)
    const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null
    const maxWant = crawlerItems.reduce((m, x) => Math.max(m, Number(x.want_count || 0)), 0)
    const maxView = crawlerItems.reduce((m, x) => Math.max(m, Number(x.view_count || 0)), 0)
    return {
      avgPrice,
      maxWant,
      maxView,
    }
  }, [crawlerItems])

  const topWant = useMemo(() => topN(crawlerItems, 'want_count', 8), [crawlerItems])
  const topView = useMemo(() => topN(crawlerItems, 'view_count', 8), [crawlerItems])

  const crawlerJobOptions = useMemo(() => {
    return crawlerJobs.map((job) => ({
      value: job.id.toString(),
      label: `${job.keyword} · ${job.cookie_id}${typeof job.item_count === 'number' ? `（${job.item_count}）` : ''}`,
    }))
  }, [crawlerJobs])

  const selectedCrawlerJob = useMemo(
    () => crawlerJobs.find((job) => job.id === selectedCrawlerJobId),
    [crawlerJobs, selectedCrawlerJobId],
  )

  const loadCrawlerItems = async (jobId?: number) => {
    if (!jobId) {
      setCrawlerItems([])
      return
    }
    try {
      setLoadingCrawlerItems(true)
      const res = await listGoofishCrawlItems(jobId, { limit: 100 })
      setCrawlerItems(res.items || [])
    } catch {
      setCrawlerItems([])
      addToast({ type: 'error', message: '加载采集结果失败' })
    } finally {
      setLoadingCrawlerItems(false)
    }
  }

  useEffect(() => {
    loadCrawlerItems(selectedCrawlerJobId)
  }, [selectedCrawlerJobId])


  if (loadingPage) return <PageLoading />

  const maxWant = Math.max(1, ...topWant.map((x) => Number(x.want_count || 0)))
  const maxView = Math.max(1, ...topView.map((x) => Number(x.view_count || 0)))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">数据罗盘</h1>
          <p className="page-description">查看定时采集的 Goofish 商品数据，进行爆款/关键词分析</p>
        </div>
      </div>

      <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="vben-card">
        <div className="vben-card-header flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="vben-card-title">采集任务选择</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">选择要分析的任务</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="btn-ios-secondary !px-2 !py-1.5 text-xs inline-flex items-center gap-1"
              onClick={async () => {
                await loadCrawlerJobs({ keepSelection: true })
                await loadCrawlerItems(selectedCrawlerJobId)
              }}
              disabled={loadingCrawlerJobs || loadingCrawlerItems}
              title="刷新任务与结果"
            >
              <RefreshCw className={`w-4 h-4 ${loadingCrawlerJobs ? 'animate-spin' : ''}`} />
              刷新
            </button>
          </div>
        </div>
        <div className="vben-card-body space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <Select
              value={selectedCrawlerJobId?.toString() || ''}
              onChange={(value) => setSelectedCrawlerJobId(Number(value))}
              options={[
                { value: '', label: '请选择任务' },
                ...crawlerJobOptions,
              ]}
              placeholder="请选择任务"
            />
            {selectedCrawlerJobId && (
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="text-slate-500 dark:text-slate-400">
                  最新运行: {formatDateTime(selectedCrawlerJob?.last_run_at)}
                </span>
                <span className="text-slate-500 dark:text-slate-400">
                  最近采集: {formatDateTime(selectedCrawlerJob?.latest_item_fetched_at)}
                </span>
                <span className="text-slate-500 dark:text-slate-400">
                  已采集: {selectedCrawlerJob?.item_count ?? 0}
                </span>
                {selectedCrawlerJob?.enabled === false ? (
                  <span className="text-amber-600 dark:text-amber-400">任务已停用</span>
                ) : selectedCrawlerJob?.running ? (
                  <span className="text-emerald-600 dark:text-emerald-400">运行中</span>
                ) : (
                  <span className="text-amber-600 dark:text-amber-400">未运行</span>
                )}
                {selectedCrawlerJob?.last_error && (
                  <span className="text-red-600 dark:text-red-400 truncate max-w-[28rem]" title={selectedCrawlerJob.last_error}>
                    错误: {selectedCrawlerJob.last_error}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard icon={BarChart3} label="已采集条数" value={`${crawlerItems.length}`} />
        <StatCard icon={TrendingUp} label="最高想要数" value={`${stats.maxWant}`} />
        <StatCard icon={TrendingUp} label="最高浏览量" value={`${stats.maxView}`} />
        <StatCard
          icon={Filter}
          label="均价（估算）"
          value={stats.avgPrice === null ? '-' : `¥${stats.avgPrice.toFixed(2)}`}
        />
      </div>

      {(topWant.length > 0 || topView.length > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="vben-card">
            <div className="vben-card-header">
              <h2 className="vben-card-title">爆款 TOP（按想要数）</h2>
            </div>
            <div className="vben-card-body space-y-2">
              {topWant.map((x) => (
                <div key={x.item_id} className="flex items-center gap-3">
                  <div className="w-12 text-xs text-slate-500 dark:text-slate-400 shrink-0">
                    {x.want_count || 0}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded">
                      <div
                        className="h-2 bg-blue-500 rounded"
                        style={{ width: `${Math.round((Number(x.want_count || 0) / maxWant) * 100)}%` }}
                      />
                    </div>
                    <div className="text-xs text-slate-700 dark:text-slate-200 truncate mt-1">{x.title}</div>
                  </div>
                  {x.item_url && (
                    <a
                      href={x.item_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-slate-400 hover:text-blue-600"
                      title="打开商品链接"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="vben-card">
            <div className="vben-card-header">
              <h2 className="vben-card-title">热度 TOP（按浏览量）</h2>
            </div>
            <div className="vben-card-body space-y-2">
              {topView.map((x) => (
                <div key={x.item_id} className="flex items-center gap-3">
                  <div className="w-12 text-xs text-slate-500 dark:text-slate-400 shrink-0">
                    {x.view_count || 0}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded">
                      <div
                        className="h-2 bg-emerald-500 rounded"
                        style={{ width: `${Math.round((Number(x.view_count || 0) / maxView) * 100)}%` }}
                      />
                    </div>
                    <div className="text-xs text-slate-700 dark:text-slate-200 truncate mt-1">{x.title}</div>
                  </div>
                  {x.item_url && (
                    <a
                      href={x.item_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-slate-400 hover:text-blue-600"
                      title="打开商品链接"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="vben-card">
        <div className="vben-card-header flex items-center justify-between gap-3">
          <h2 className="vben-card-title">商品明细</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">排序</span>
            <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)} className="input-ios h-9">
              <option value="want_desc">想要数（高→低）</option>
              <option value="view_desc">浏览量（高→低）</option>
              <option value="price_desc">价格（高→低）</option>
              <option value="price_asc">价格（低→高）</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="table-ios">
            <thead>
              <tr>
                <th>标题</th>
                <th>价格</th>
                <th>地区</th>
                <th>想要数</th>
                <th>浏览量</th>
                <th>描述（截断）</th>
                <th>链接</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="empty-state py-10">
                      <RefreshCw className="empty-state-icon" />
                      <p className="text-gray-500">
                        {loadingCrawlerItems ? '加载中...' : selectedCrawlerJobId ? '暂无采集数据' : '请选择采集任务'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                sortedItems.map((x) => (
                  <tr key={`${x.item_id}-${x.job_id}`}>
                    <td className="max-w-[28rem]">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900 dark:text-slate-100 line-clamp-2">{x.title}</span>
                        {x.detail_error && (
                          <span className="text-xs text-amber-600 dark:text-amber-400" title={x.detail_error}>
                            详情失败
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="text-red-500 font-semibold whitespace-nowrap">{x.price || '-'}</td>
                    <td className="whitespace-nowrap">{x.area || '-'}</td>
                    <td className="whitespace-nowrap">{Number(x.want_count || 0)}</td>
                    <td className="whitespace-nowrap">{x.view_count ?? '-'}</td>
                    <td className="max-w-[32rem] text-slate-600 dark:text-slate-300">
                      <span className="line-clamp-2">{x.description || '-'}</span>
                    </td>
                    <td className="whitespace-nowrap">
                      {x.item_url ? (
                        <a
                          href={x.item_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700"
                        >
                          打开 <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  )
}
