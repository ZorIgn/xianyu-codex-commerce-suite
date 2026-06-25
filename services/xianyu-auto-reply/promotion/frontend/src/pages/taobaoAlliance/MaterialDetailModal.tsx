/**
 * 素材库 - 查看明细弹窗
 *
 * 功能：
 * 1. 展示素材完整信息（图片轮播、价格、描述、链接、淘口令等）
 * 2. 快捷复制淘口令/推广链接
 */
import { useState, useEffect } from 'react'
import { X, ChevronLeft, ChevronRight, Copy, ExternalLink, Store, Smartphone } from 'lucide-react'
import type { Material } from '@/api/material'
import { useUIStore } from '@/store/uiStore'

const publishStatusTextMap: Record<Material['publish_status'], string> = {
  unpublished: '未发布',
  published: '已发布',
  failed: '发布失败',
}

interface Props {
  material: Material
  onClose: () => void
}

/** 素材明细弹窗 */
export function MaterialDetailModal({ material, onClose }: Props) {
  const { addToast } = useUIStore()
  const [imgIndex, setImgIndex] = useState(0)
  const images = material.images || []

  /** 复制文本 */
  const handleCopy = async (text: string, label: string) => {
    if (!text) { addToast({ type: 'warning', message: `暂无${label}` }); return }
    try {
      await navigator.clipboard.writeText(text)
      addToast({ type: 'success', message: `${label}已复制` })
    } catch {
      addToast({ type: 'error', message: '复制失败' })
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
        className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-[90vw] max-w-lg max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-slate-700 flex-shrink-0">
          <h2 className="text-base font-semibold">素材明细</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-slate-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* 图片轮播 */}
          {images.length > 0 && (
            <div className="relative aspect-square rounded-lg overflow-hidden bg-gray-100 dark:bg-slate-700">
              <img
                src={images[imgIndex]}
                alt={material.title}
                className="w-full h-full object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23f3f4f6" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%239ca3af" font-size="14">暂无图片</text></svg>'
                }}
              />
              {images.length > 1 && (
                <>
                  <button
                    onClick={() => setImgIndex((i) => (i - 1 + images.length) % images.length)}
                    className="absolute left-2 top-1/2 -translate-y-1/2 p-1.5 bg-black/40 text-white rounded-full hover:bg-black/60"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => setImgIndex((i) => (i + 1) % images.length)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-black/40 text-white rounded-full hover:bg-black/60"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                  <span className="absolute bottom-2 right-2 px-2 py-0.5 text-xs bg-black/50 text-white rounded-full">
                    {imgIndex + 1}/{images.length}
                  </span>
                </>
              )}
            </div>
          )}

          {/* 标题 */}
          <h3 className="text-sm font-medium leading-5">{material.title}</h3>

          {/* 价格行 */}
          <div className="flex items-baseline gap-3">
            <div className="flex items-baseline gap-1">
              <span className="text-xs text-gray-400">售价</span>
              <span className="text-xl font-bold text-red-500">¥{material.price}</span>
            </div>
            {material.original_price && (
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-gray-400">原价</span>
                <span className="text-sm text-gray-400 line-through">¥{material.original_price}</span>
              </div>
            )}
            {material.promotion_price && (
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-gray-400">到手价</span>
                <span className="text-lg font-bold text-green-600">¥{material.promotion_price}</span>
              </div>
            )}
          </div>

          {/* 佣金 / 销量 / 店铺 */}
          <div className="space-y-2">
            {material.shop_title && (
              <div className="flex items-center gap-1.5 text-sm text-gray-500">
                <Store className="w-4 h-4 flex-shrink-0" />
                <span>{material.shop_title}</span>
              </div>
            )}
          </div>

          {/* 商品描述 */}
          {material.description && (
            <div>
              <div className="text-xs font-medium text-gray-400 mb-1">商品描述</div>
              <div className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-line bg-gray-50 dark:bg-slate-700/50 rounded-lg p-3">
                {material.description}
              </div>
            </div>
          )}

          {/* 优惠券信息 */}
          {material.coupon_info && (
            <div>
              <div className="text-xs font-medium text-gray-400 mb-1">优惠券信息</div>
              <div className="text-sm text-orange-600 dark:text-orange-400 whitespace-pre-line bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3">
                {material.coupon_info}
              </div>
            </div>
          )}

          {/* 淘口令 */}
          {material.tpwd && (
            <div>
              <div className="text-xs font-medium text-gray-400 mb-1">淘口令</div>
              <div className="flex items-center gap-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg px-3 py-2">
                <Smartphone className="w-4 h-4 text-orange-500 flex-shrink-0" />
                <span className="text-sm text-orange-700 dark:text-orange-400 font-mono select-all flex-1">{material.tpwd}</span>
                <button
                  onClick={() => handleCopy(material.tpwd, '淘口令')}
                  className="p-1 text-orange-500 hover:text-orange-700"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* 推广链接 */}
          {(material.click_url || material.coupon_url || material.short_url) && (
            <div>
              <div className="text-xs font-medium text-gray-400 mb-1">推广链接</div>
              <div className="space-y-1.5">
                {material.short_url && (
                  <div className="flex items-center gap-2 text-xs bg-gray-50 dark:bg-slate-700/50 rounded-lg px-3 py-2">
                    <span className="text-gray-400 flex-shrink-0">短连接</span>
                    <span className="font-mono text-gray-600 dark:text-gray-300 truncate flex-1">{material.short_url}</span>
                    <button onClick={() => handleCopy(material.short_url, '短连接')} className="text-blue-500 flex-shrink-0">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                {material.coupon_url && (
                  <div className="flex items-center gap-2 text-xs bg-gray-50 dark:bg-slate-700/50 rounded-lg px-3 py-2">
                    <span className="text-gray-400 flex-shrink-0">券链接</span>
                    <span className="font-mono text-gray-600 dark:text-gray-300 truncate flex-1">{material.coupon_url}</span>
                    <button onClick={() => handleCopy(material.coupon_url, '券链接')} className="text-blue-500 flex-shrink-0">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                {material.click_url && (
                  <div className="flex items-center gap-2 text-xs bg-gray-50 dark:bg-slate-700/50 rounded-lg px-3 py-2">
                    <span className="text-gray-400 flex-shrink-0">推广链接</span>
                    <span className="font-mono text-gray-600 dark:text-gray-300 truncate flex-1">{material.click_url}</span>
                    <button onClick={() => handleCopy(material.click_url, '推广链接')} className="text-blue-500 flex-shrink-0">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 商品ID / 时间 */}
          <div className="text-xs text-gray-400 space-y-1 pt-2 border-t border-gray-100 dark:border-slate-700">
            <div>商品ID: {material.item_id}</div>
            <div>发布后商品ID: {material.published_item_id || '-'}</div>
            <div>随机字符: {material.publish_random_str || '-'}</div>
            <div>发布状态: {publishStatusTextMap[material.publish_status]}</div>
            {material.published_at && <div>发布时间: {material.published_at}</div>}
            <div>创建时间: {material.created_at}</div>
            {material.updated_at && material.updated_at !== material.created_at && (
              <div>更新时间: {material.updated_at}</div>
            )}
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-gray-200 dark:border-slate-700 flex-shrink-0">
          {material.tpwd && (
            <button
              onClick={() => handleCopy(material.tpwd, '淘口令')}
              className="btn-ios-secondary flex items-center gap-1.5 flex-1 justify-center"
            >
              <Smartphone className="w-4 h-4" />复制淘口令
            </button>
          )}
          {material.short_url && (
            <button
              onClick={() => handleCopy(material.short_url, '短连接')}
              className="btn-ios-secondary flex items-center gap-1.5 flex-1 justify-center"
            >
              <Copy className="w-4 h-4" />复制短连接
            </button>
          )}
          <button
            onClick={() => handleCopy(material.coupon_url || material.click_url, '推广链接')}
            className="btn-ios-secondary flex items-center gap-1.5 flex-1 justify-center"
          >
            <Copy className="w-4 h-4" />复制链接
          </button>
          {(material.coupon_url || material.click_url) && (
            <a
              href={material.coupon_url || material.click_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ios-primary flex items-center gap-1.5 flex-1 justify-center"
            >
              <ExternalLink className="w-4 h-4" />打开链接
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
