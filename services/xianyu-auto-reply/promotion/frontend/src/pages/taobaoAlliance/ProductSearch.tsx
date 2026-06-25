/**
 * 淘宝联盟 - 选品广场页面
 *
 * 功能：
 * 1. 关键词搜索商品（调用淘宝开放平台API）
 * 2. 商品卡片网格展示（图片、价格、佣金率、店铺等）
 * 3. 排序切换
 * 4. 分页加载
 */
import { useState, useCallback } from 'react'
import { Search, Store, Tag, Loader2, Copy, Link, Filter, ChevronDown, ChevronUp } from 'lucide-react'
import { searchProducts } from '@/api/taobaoAlliance'
import type { Product } from '@/api/taobaoAlliance'
import { useUIStore } from '@/store/uiStore'
import { ProductDetailModal } from './ProductDetailModal'

/** 淘宝常用商品类目（cat参数） */
const CATEGORY_OPTIONS = [
  { id: '', label: '全部类目' },
  // 服饰鞋包
  { id: '16', label: '女装/女士精品' },
  { id: '30', label: '男装' },
  { id: '50006843', label: '女鞋' },
  { id: '50011740', label: '流行男鞋' },
  { id: '1625', label: '内衣/家居服' },
  { id: '50006842', label: '箱包皮具/女包/男包' },
  { id: '50010404', label: '服饰配件/帽子/围巾' },
  { id: '50012029', label: '运动鞋' },
  // 运动户外
  { id: '50010728', label: '运动/瑜伽/健身' },
  { id: '50013886', label: '户外/登山/旅行' },
  // 手机数码
  { id: '1512', label: '手机' },
  { id: '1101', label: '笔记本电脑' },
  { id: '11', label: '电脑硬件/显示器/周边' },
  { id: '50008090', label: '3C数码配件' },
  { id: '14', label: '数码相机/摄像机' },
  // 家用电器
  { id: '50022703', label: '大家电' },
  { id: '50012100', label: '生活电器' },
  { id: '50012082', label: '厨房电器' },
  { id: '50011972', label: '影音电器' },
  { id: '50002768', label: '个人护理/按摩器材' },
  // 美妆饰品
  { id: '1801', label: '美容护肤/美体/精油' },
  { id: '50010788', label: '彩妆/香水/美妆工具' },
  { id: '50023282', label: '美发护发/假发' },
  { id: '50011397', label: '珠宝/钻石/翡翠/黄金' },
  { id: '50005700', label: '品牌手表/流行手表' },
  { id: '28', label: '眼镜/瑞士军刀' },
  // 食品百货
  { id: '50002766', label: '零食/坚果/特产' },
  { id: '50016422', label: '粮油米面/调味品' },
  { id: '50026316', label: '茶/酒/冲饮' },
  { id: '50020275', label: '传统滋补营养品' },
  // 家居日用
  { id: '21', label: '居家日用/创意礼品' },
  { id: '50016349', label: '厨房/餐饮用具' },
  { id: '50016348', label: '清洁/卫浴/收纳' },
  { id: '50008163', label: '床上用品/布艺软饰' },
  { id: '50020808', label: '家居饰品' },
  { id: '50008164', label: '住宅家具' },
  { id: '50025705', label: '洗护清洁剂/纸品/香薰' },
  // 家装建材
  { id: '27', label: '家装主材' },
  { id: '50020485', label: '五金/工具' },
  // 母婴亲子
  { id: '35', label: '奶粉/辅食/营养品' },
  { id: '50008165', label: '童装/童鞋/亲子装' },
  { id: '25', label: '玩具/模型/动漫/益智' },
  { id: '50014812', label: '尿片/洗护/喂哺/推车' },
  // 其他
  { id: '33', label: '书籍/杂志/报纸' },
  { id: '29', label: '宠物/宠物食品及用品' },
  { id: '50017300', label: '乐器/吉他/钢琴' },
  { id: '50007216', label: '鲜花速递/绿植园艺' },
  { id: '26', label: '汽车用品/配件/改装' },
]

/** 排序选项定义（升级版API支持的所有排序字段） */
const DEFAULT_SORT_OPTIONS = [
  { key: 'default', label: '默认排序' },
  { key: 'total_sales_des', label: '销量降序' },
  { key: 'total_sales_asc', label: '销量升序' },
  { key: 'tk_rate_des', label: '收入率降序' },
  { key: 'tk_rate_asc', label: '收入率升序' },
  { key: 'tk_mkt_rate_des', label: '营销佣金降序' },
  { key: 'tk_mkt_rate_asc', label: '营销佣金升序' },
  { key: 'tk_total_sales_des', label: '累计推广量降序' },
  { key: 'tk_total_sales_asc', label: '累计推广量升序' },
  { key: 'tk_total_commi_des', label: '总支出佣金降序' },
  { key: 'tk_total_commi_asc', label: '总支出佣金升序' },
  { key: 'final_promotion_price_asc', label: '到手价升序' },
  { key: 'final_promotion_price_des', label: '到手价降序' },
  { key: 'match_des', label: '匹配分降序' },
  { key: 'match_asc', label: '匹配分升序' },
]

export function ProductSearch() {
  const { addToast } = useUIStore()
  const [keyword, setKeyword] = useState('')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [sort, setSort] = useState('default')
  const [hasSearched, setHasSearched] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  /** 筛选条件 */
  const [showFilters, setShowFilters] = useState(true)
  const [hasCoupon, setHasCoupon] = useState(false)
  const [needFreeShipment, setNeedFreeShipment] = useState(false)
  const [isTmall, setIsTmall] = useState(false)
  const [startPrice, setStartPrice] = useState('')
  const [endPrice, setEndPrice] = useState('')
  const [startTkRate, setStartTkRate] = useState('')
  const [endTkRate, setEndTkRate] = useState('')
  const [cat, setCat] = useState('')

  /** 执行搜索 */
  const doSearch = useCallback(async (
    kw: string = searchKeyword,
    p: number = page,
    s: string = sort,
  ) => {
    setLoading(true)
    setHasSearched(true)
    try {
      const res = await searchProducts({
        keyword: kw.trim(),
        page: p,
        page_size: pageSize,
        sort: s,
        has_coupon: hasCoupon || undefined,
        need_free_shipment: needFreeShipment || undefined,
        is_tmall: isTmall || undefined,
        start_price: startPrice ? Number(startPrice) : undefined,
        end_price: endPrice ? Number(endPrice) : undefined,
        start_tk_rate: startTkRate ? Math.round(Number(startTkRate) * 100) : undefined,
        end_tk_rate: endTkRate ? Math.round(Number(endTkRate) * 100) : undefined,
        cat: cat || undefined,
      })
      if (res.success && res.data) {
        setProducts(res.data.products)
        setTotal(res.data.total)
      } else {
        addToast({ type: 'error', message: res.message || '搜索失败' })
        setProducts([])
      }
    } catch {
      addToast({ type: 'error', message: '搜索请求失败' })
      setProducts([])
    } finally {
      setLoading(false)
    }
  }, [searchKeyword, page, sort, pageSize, addToast, hasCoupon, needFreeShipment, isTmall, startPrice, endPrice, startTkRate, endTkRate, cat])

  /** 提交搜索 */
  const handleSearch = () => {
    setSearchKeyword(keyword.trim())
    setPage(1)
    doSearch(keyword.trim(), 1, sort)
  }

  /** 回车搜索 */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  /** 排序切换 */
  const handleSortChange = (newSort: string) => {
    setSort(newSort)
    setPage(1)
    doSearch(searchKeyword, 1, newSort)
  }

  /** 分页 */
  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    doSearch(searchKeyword, newPage, sort)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-4">
      {/* 页头 */}
      <div className="page-header">
        <h1 className="page-title">选品广场</h1>
        <p className="page-description">搜索淘宝联盟商品，查看佣金信息</p>
      </div>

      {/* 搜索栏 */}
      <div className="vben-card">
        <div className="vben-card-body space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* 搜索输入 */}
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入关键词搜索商品..."
                className="input-ios w-full pl-10 pr-4 py-2"
              />
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`btn-ios-secondary flex items-center gap-1 ${
                (hasCoupon || needFreeShipment || isTmall || startPrice || endPrice || startTkRate || endTkRate || cat)
                  ? 'text-orange-600 border-orange-300' : ''
              }`}
            >
              <Filter className="w-4 h-4" />
              筛选
              {showFilters ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            <button
              onClick={handleSearch}
              disabled={loading}
              className="btn-ios-primary flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              搜索
            </button>
          </div>

          {/* 筛选面板 */}
          {showFilters && (
            <div className="border-t border-gray-200 dark:border-slate-700 pt-3 space-y-3">
              {/* 商品类目 */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500 w-16">商品类目</span>
                <select value={cat} onChange={(e) => setCat(e.target.value)}
                  className="input-ios px-2 py-1 text-sm min-w-[160px]">
                  {CATEGORY_OPTIONS.map((c) => (
                    <option key={c.id} value={c.id}>{c.label}</option>
                  ))}
                </select>
              </div>
              {/* 快捷筛选 */}
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input type="checkbox" checked={hasCoupon} onChange={(e) => setHasCoupon(e.target.checked)}
                    className="rounded border-gray-300 text-orange-500 focus:ring-orange-500" />
                  有优惠券
                </label>
                <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input type="checkbox" checked={needFreeShipment} onChange={(e) => setNeedFreeShipment(e.target.checked)}
                    className="rounded border-gray-300 text-orange-500 focus:ring-orange-500" />
                  包邮
                </label>
                <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input type="checkbox" checked={isTmall} onChange={(e) => setIsTmall(e.target.checked)}
                    className="rounded border-gray-300 text-orange-500 focus:ring-orange-500" />
                  天猫
                </label>
              </div>
              {/* 价格范围 */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500 w-16">价格范围</span>
                <input type="number" min="0" step="1" value={startPrice} onChange={(e) => setStartPrice(e.target.value)}
                  placeholder="最低价" className="input-ios w-24 px-2 py-1 text-sm" />
                <span className="text-gray-400">-</span>
                <input type="number" min="0" step="1" value={endPrice} onChange={(e) => setEndPrice(e.target.value)}
                  placeholder="最高价" className="input-ios w-24 px-2 py-1 text-sm" />
                <span className="text-xs text-gray-400">元</span>
              </div>
              {/* 佣金率范围 */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500 w-16">佣金率</span>
                <input type="number" min="0" step="0.5" value={startTkRate} onChange={(e) => setStartTkRate(e.target.value)}
                  placeholder="最低" className="input-ios w-24 px-2 py-1 text-sm" />
                <span className="text-gray-400">-</span>
                <input type="number" min="0" step="0.5" value={endTkRate} onChange={(e) => setEndTkRate(e.target.value)}
                  placeholder="最高" className="input-ios w-24 px-2 py-1 text-sm" />
                <span className="text-xs text-gray-400">%</span>
              </div>
              {/* 重置筛选 */}
              <div className="flex justify-end">
                <button onClick={() => {
                  setHasCoupon(false); setNeedFreeShipment(false); setIsTmall(false)
                  setStartPrice(''); setEndPrice(''); setStartTkRate(''); setEndTkRate(''); setCat('')
                }} className="text-xs text-gray-500 hover:text-orange-500 transition-colors">
                  重置筛选
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 排序栏 */}
      {hasSearched && (
        <div className="vben-card">
          <div className="vben-card-body py-2">
            <div className="flex flex-wrap items-center gap-1">
              {DEFAULT_SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => handleSortChange(opt.key)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    sort === opt.key
                      ? 'bg-orange-500 text-white'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
              <span className="ml-auto text-sm text-gray-500">
                共 {total} 件商品
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 商品列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">搜索中...</span>
        </div>
      ) : products.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {products.map((product, idx) => (
            <ProductCard key={`${product.title}-${idx}`} product={product} onDetail={setSelectedProduct} />
          ))}
        </div>
      ) : hasSearched ? (
        <div className="vben-card">
          <div className="vben-card-body flex flex-col items-center py-16">
            <Search className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-500">未找到相关商品</p>
          </div>
        </div>
      ) : (
        <div className="vben-card">
          <div className="vben-card-body flex flex-col items-center py-16">
            <Search className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-500">输入关键词开始搜索</p>
          </div>
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 py-4">
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            className="btn-ios-secondary btn-sm"
          >
            上一页
          </button>
          <span className="px-4 text-sm text-gray-600 dark:text-gray-400">
            第 {page} / {totalPages} 页
          </span>
          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            className="btn-ios-secondary btn-sm"
          >
            下一页
          </button>
        </div>
      )}
      {/* 商品详情弹窗 */}
      {selectedProduct && (
        <ProductDetailModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      )}
    </div>
  )
}


/** 商品卡片组件 */
function ProductCard({ product, onDetail }: { product: Product; onDetail: (p: Product) => void }) {
  const { addToast } = useUIStore()

  /** 复制推广链接，优先券二合一链接 */
  const handleCopyLink = async () => {
    const link = product.coupon_share_url || product.click_url
    if (!link) {
      addToast({ type: 'warning', message: '该商品暂无推广链接' })
      return
    }
    try {
      await navigator.clipboard.writeText(link)
      addToast({ type: 'success', message: '推广链接已复制' })
    } catch {
      addToast({ type: 'error', message: '复制失败，请手动复制' })
    }
  }
  const platformBadge = product.user_type === 1
    ? { label: '天猫', className: 'bg-red-500 text-white' }
    : product.user_type === 3
    ? { label: '特价版', className: 'bg-purple-500 text-white' }
    : { label: '淘宝', className: 'bg-orange-500 text-white' }

  return (
    <div className="vben-card group hover:shadow-lg transition-shadow duration-200 overflow-hidden cursor-pointer" onClick={() => onDetail(product)}>
      {/* 商品图片 */}
      <div className="relative aspect-square overflow-hidden bg-gray-100 dark:bg-slate-800">
        <img
          src={product.pic || product.white_image}
          alt={product.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23f3f4f6" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%239ca3af" font-size="14">暂无图片</text></svg>'
          }}
        />
        {/* 平台标识 */}
        <span className={`absolute top-2 left-2 px-1.5 py-0.5 text-xs font-medium rounded ${platformBadge.className}`}>
          {platformBadge.label}
        </span>
        {/* 促销标签 */}
        {product.promotion_tags.length > 0 && (
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-1">
            {product.promotion_tags.slice(0, 3).map((tag, i) => (
              <span key={i} className="px-1.5 py-0.5 text-xs bg-orange-100 text-orange-600 rounded border border-orange-200">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 商品信息 */}
      <div className="p-3 space-y-2">
        {/* 标题 */}
        <h3 className="text-sm font-medium text-gray-800 dark:text-gray-200 line-clamp-2 leading-5 min-h-[40px]">
          {product.title}
        </h3>

        {/* 价格行 */}
        <div className="flex items-baseline gap-2">
          <span className="text-xs text-gray-400">到手价</span>
          <span className="text-lg font-bold text-red-500">
            ¥{product.promotion_price || product.zk_final_price}
          </span>
          {product.promotion_price && product.price && Number(product.promotion_price) < Number(product.price) && (
            <span className="text-xs text-gray-400 line-through">¥{product.price}</span>
          )}
        </div>

        {/* 佣金信息 */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1">
            <Tag className="w-3 h-3 text-orange-500" />
            <span className="text-orange-600 dark:text-orange-400 font-medium">
              收入 {product.income_rate}
            </span>
          </div>
          <span className="text-green-600 dark:text-green-400 font-medium">
            赚 {product.total_earn}
          </span>
        </div>

        {/* 佣金明细 */}
        <div className="text-xs text-gray-400 flex items-center gap-2">
          <span>佣金{product.commission_rate}</span>
          {product.subsidy_amount && product.subsidy_amount !== '¥0' && (
            <span className="text-blue-500">补贴{product.subsidy_amount}</span>
          )}
        </div>

        {/* 销量信息 */}
        <div className="text-xs text-gray-400 flex items-center justify-between">
          <span>月30天销量 {product.volume}</span>
          {product.annual_vol && (
            <span>年销 {product.annual_vol}</span>
          )}
        </div>

        {/* 店铺 */}
        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 truncate">
          <Store className="w-3 h-3 flex-shrink-0" />
          <span className="truncate">{product.shop_title}</span>
          {product.brand_name && (
            <span className="text-blue-500 flex-shrink-0">{product.brand_name}</span>
          )}
        </div>

        {/* 优惠路径 */}
        {product.promotion_path.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {product.promotion_path.map((p, i) => (
              <span key={i} className="px-1.5 py-0.5 text-xs bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400 rounded">
                {p.title}: {p.desc}
              </span>
            ))}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={(e) => { e.stopPropagation(); handleCopyLink() }}
            className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-md transition-colors"
          >
            <Copy className="w-3 h-3" />
            复制推广链接
          </button>
          {(product.coupon_share_url || product.click_url) && (
            <a
              href={product.coupon_share_url || product.click_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center justify-center px-2 py-1.5 text-xs font-medium text-orange-600 border border-orange-300 hover:bg-orange-50 dark:hover:bg-orange-900/20 rounded-md transition-colors"
              title="打开推广链接"
            >
              <Link className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
