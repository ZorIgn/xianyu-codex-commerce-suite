/**
 * 淘宝联盟 - 商品详情弹窗
 *
 * 功能：
 * 1. 点击商品卡片后弹出，展示商品详情
 * 2. 多张商品图片左右切换
 * 3. 价格、佣金、促销路径等信息展示
 * 4. 推广链接复制和打开
 */
import { useState, useEffect, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight, Loader2, Copy, ExternalLink, Store, MapPin, Tag, Smartphone } from 'lucide-react'
import { getProductDetail, createTpwd } from '@/api/taobaoAlliance'
import type { Product, ProductDetail } from '@/api/taobaoAlliance'
import { useUIStore } from '@/store/uiStore'

interface Props {
  /** 搜索结果中的商品基础信息 */
  product: Product
  /** 关闭弹窗 */
  onClose: () => void
}

/** 商品详情弹窗 */
export function ProductDetailModal({ product, onClose }: Props) {
  const { addToast } = useUIStore()
  const [detail, setDetail] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [imgIndex, setImgIndex] = useState(0)
  const [tpwd, setTpwd] = useState('')
  const [tpwdLoading, setTpwdLoading] = useState(false)

  /** 获取商品详情 */
  const fetchDetail = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getProductDetail(product.item_id)
      if (res.success && res.data) {
        setDetail(res.data)
      }
    } catch {
      // 详情获取失败不影响基本展示
    } finally {
      setLoading(false)
    }
  }, [product.item_id])

  useEffect(() => { fetchDetail() }, [fetchDetail])

  // 图片列表：优先使用详情API的多图，回退到搜索结果主图
  const images = (detail?.images?.length ? detail.images : [product.pic]).filter(Boolean)

  /** 切换图片 */
  const prevImg = () => setImgIndex((i) => (i > 0 ? i - 1 : images.length - 1))
  const nextImg = () => setImgIndex((i) => (i < images.length - 1 ? i + 1 : 0))

  /** 复制推广链接 */
  const copyLink = async () => {
    const url = product.coupon_share_url || product.click_url
    if (!url) { addToast({ type: 'warning', message: '暂无推广链接' }); return }
    try {
      await navigator.clipboard.writeText(url)
      addToast({ type: 'success', message: '推广链接已复制' })
    } catch {
      addToast({ type: 'error', message: '复制失败' })
    }
  }

  /** 打开推广链接 */
  const openLink = () => {
    const url = product.coupon_share_url || product.click_url
    if (url) window.open(url, '_blank')
    else addToast({ type: 'warning', message: '暂无推广链接' })
  }

  /** 生成并复制淘口令 */
  const handleCopyTpwd = async () => {
    // 如果已经生成过，直接复制
    if (tpwd) {
      try {
        await navigator.clipboard.writeText(tpwd)
        addToast({ type: 'success', message: '淘口令已复制' })
      } catch {
        addToast({ type: 'error', message: '复制失败' })
      }
      return
    }
    const url = product.coupon_share_url || product.click_url
    if (!url) { addToast({ type: 'warning', message: '暂无推广链接，无法生成淘口令' }); return }
    setTpwdLoading(true)
    try {
      const res = await createTpwd({ url, text: product.title, logo: product.pic })
      if (res.success && res.data?.tpwd) {
        setTpwd(res.data.tpwd)
        await navigator.clipboard.writeText(res.data.tpwd)
        addToast({ type: 'success', message: `淘口令已复制: ${res.data.tpwd}` })
      } else {
        addToast({ type: 'error', message: res.message || '淘口令生成失败' })
      }
    } catch {
      addToast({ type: 'error', message: '淘口令生成请求失败' })
    } finally {
      setTpwdLoading(false)
    }
  }

  /** ESC关闭 */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') e.preventDefault() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-[90vw] max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 顶栏 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-slate-700">
          <h2 className="text-base font-semibold truncate flex-1 mr-3">商品详情</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 内容区（可滚动） */}
        <div className="overflow-y-auto flex-1 p-5 space-y-4">
          {/* 图片区 + 基本信息 */}
          <div className="flex flex-col sm:flex-row gap-4">
            {/* 图片轮播 */}
            <div className="relative w-full sm:w-64 h-64 flex-shrink-0 bg-gray-50 dark:bg-slate-900 rounded-lg overflow-hidden">
              {loading && !images.length ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
                </div>
              ) : (
                <>
                  <img src={images[imgIndex]} alt="" className="w-full h-full object-contain" />
                  {images.length > 1 && (
                    <>
                      <button onClick={prevImg} className="absolute left-1 top-1/2 -translate-y-1/2 bg-black/40 text-white rounded-full p-1 hover:bg-black/60">
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <button onClick={nextImg} className="absolute right-1 top-1/2 -translate-y-1/2 bg-black/40 text-white rounded-full p-1 hover:bg-black/60">
                        <ChevronRight className="w-4 h-4" />
                      </button>
                      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-xs text-white bg-black/50 rounded-full px-2 py-0.5">
                        {imgIndex + 1} / {images.length}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* 基本信息 */}
            <div className="flex-1 space-y-2 min-w-0">
              <h3 className="text-base font-semibold leading-snug">{product.title}</h3>
              {product.short_title && product.short_title !== product.title && (
                <p className="text-sm text-gray-500">{product.short_title}</p>
              )}

              {/* 价格区 */}
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-2xl font-bold text-red-500">¥{product.promotion_price}</span>
                {product.zk_final_price !== product.promotion_price && (
                  <span className="text-sm text-gray-400 line-through">¥{product.zk_final_price}</span>
                )}
                {product.price !== product.zk_final_price && (
                  <span className="text-xs text-gray-400 line-through">¥{product.price}</span>
                )}
              </div>

              {/* 标签 */}
              {product.promotion_tags?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {product.promotion_tags.map((tag, i) => (
                    <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-orange-50 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400">{tag}</span>
                  ))}
                </div>
              )}

              {/* 店铺/发货地 */}
              <div className="flex flex-wrap gap-3 text-sm text-gray-500">
                <span className="flex items-center gap-1">
                  <Store className="w-3.5 h-3.5" />
                  {product.shop_title || detail?.shop_title || '-'}
                  {product.user_type === 1 && <span className="text-xs text-red-500 font-semibold ml-0.5">天猫</span>}
                </span>
                {(product.provcity || detail?.provcity) && (
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" />{product.provcity || detail?.provcity}
                  </span>
                )}
              </div>

              {/* 类目 */}
              {(detail?.cat_name || product.category_name) && (
                <div className="flex items-center gap-1 text-sm text-gray-500">
                  <Tag className="w-3.5 h-3.5" />
                  {detail?.cat_name}{detail?.cat_leaf_name ? ` > ${detail.cat_leaf_name}` : ''}{!detail?.cat_name && product.category_name}
                </div>
              )}

              {/* 销量 */}
              <div className="flex flex-wrap gap-3 text-xs text-gray-400">
                <span>月销 {product.volume}</span>
                {detail?.free_shipment && <span className="text-green-500">包邮</span>}
                {product.tk_total_sales && product.tk_total_sales !== '0' && <span>累计推广 {product.tk_total_sales}</span>}
                {(product.coupon_info || detail?.coupon_info) && <span className="text-orange-500">{product.coupon_info || detail?.coupon_info}</span>}
              </div>
            </div>
          </div>

          {/* 佣金信息 */}
          <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-4 space-y-2">
            <h4 className="text-sm font-semibold text-orange-700 dark:text-orange-400">佣金信息</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <div className="text-gray-500 text-xs">收入比率</div>
                <div className="font-semibold text-orange-600">{product.income_rate}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">佣金率</div>
                <div className="font-semibold">{product.commission_rate}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">佣金金额</div>
                <div className="font-semibold">{product.commission_amount}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">预估收入</div>
                <div className="font-semibold text-red-500">{product.total_earn}</div>
              </div>
            </div>
            {product.subsidy_rate && product.subsidy_rate !== '0%' && product.subsidy_rate !== '0.00%' && (
              <div className="flex gap-4 text-sm pt-1 border-t border-orange-200 dark:border-orange-800">
                <span className="text-gray-500">补贴率: <span className="font-semibold">{product.subsidy_rate}</span></span>
                <span className="text-gray-500">补贴额: <span className="font-semibold">{product.subsidy_amount}</span></span>
              </div>
            )}
          </div>

          {/* 优惠路径 */}
          {product.promotion_path?.length > 0 && (
            <div className="bg-gray-50 dark:bg-slate-900 rounded-lg p-4 space-y-2">
              <h4 className="text-sm font-semibold">到手价优惠路径</h4>
              <div className="space-y-1">
                {product.promotion_path.map((p, i) => (
                  <div key={i} className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">{p.title} {p.desc}</span>
                    <span className="text-red-500 font-medium">-¥{p.fee}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 淘口令展示 */}
        {tpwd && (
          <div className="mx-5 mb-2 px-3 py-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg flex items-center justify-between">
            <span className="text-sm text-orange-700 dark:text-orange-400 font-mono select-all">{tpwd}</span>
            <button onClick={handleCopyTpwd} className="text-xs text-orange-600 hover:text-orange-800 ml-2 flex-shrink-0">
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* 底部操作栏 */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-gray-200 dark:border-slate-700">
          <button onClick={handleCopyTpwd} disabled={tpwdLoading}
            className="btn-ios-secondary flex items-center gap-1.5 flex-1 justify-center">
            {tpwdLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Smartphone className="w-4 h-4" />}
            {tpwd ? '复制淘口令' : '生成淘口令'}
          </button>
          <button onClick={copyLink} className="btn-ios-secondary flex items-center gap-1.5 flex-1 justify-center">
            <Copy className="w-4 h-4" />复制链接
          </button>
          <button onClick={openLink} className="btn-ios-primary flex items-center gap-1.5 flex-1 justify-center">
            <ExternalLink className="w-4 h-4" />打开链接
          </button>
        </div>
      </div>
    </div>
  )
}
