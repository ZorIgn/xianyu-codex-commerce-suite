/**
 * 素材库 - 编辑弹窗
 *
 * 功能：
 * 1. 修改素材的标题、售价、描述、图片、推广链接、淘口令
 * 2. 保存后回调刷新列表
 */
import { useState, useEffect } from 'react'
import { X, Loader2 } from 'lucide-react'
import { updateMaterial } from '@/api/material'
import type { Material } from '@/api/material'
import { useUIStore } from '@/store/uiStore'

interface Props {
  material: Material
  onClose: () => void
  onSaved: () => void
}

/** 素材编辑弹窗 */
export function MaterialEditModal({ material, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const [saving, setSaving] = useState(false)

  const [title, setTitle] = useState('')
  const [price, setPrice] = useState(0.1)
  const [description, setDescription] = useState('')
  const [images, setImages] = useState('')
  const [clickUrl, setClickUrl] = useState('')
  const [couponUrl, setCouponUrl] = useState('')
  const [couponInfo, setCouponInfo] = useState('')
  const [tpwd, setTpwd] = useState('')
  const [shortUrl, setShortUrl] = useState('')

  /** 回填 */
  useEffect(() => {
    setTitle(material.title)
    setPrice(material.price)
    setDescription(material.description)
    setImages(Array.isArray(material.images) ? material.images.join('\n') : '')
    setClickUrl(material.click_url)
    setCouponUrl(material.coupon_url)
    setCouponInfo(material.coupon_info)
    setTpwd(material.tpwd)
    setShortUrl(material.short_url)
  }, [material])

  /** 保存 */
  const handleSave = async () => {
    setSaving(true)
    try {
      const imagesJson = JSON.stringify(
        images.split('\n').map(s => s.trim()).filter(Boolean)
      )
      const res = await updateMaterial(material.id, {
        title: title.trim(),
        price,
        description: description.trim(),
        images: imagesJson,
        click_url: clickUrl.trim(),
        coupon_url: couponUrl.trim(),
        coupon_info: couponInfo.trim(),
        tpwd: tpwd.trim(),
        short_url: shortUrl.trim(),
      })
      if (res.success) {
        addToast({ type: 'success', message: '素材已更新' })
        onSaved()
        onClose()
      } else {
        addToast({ type: 'error', message: res.message || '更新失败' })
      }
    } catch {
      addToast({ type: 'error', message: '更新请求失败' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-[90vw] max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-slate-700">
          <h2 className="text-base font-semibold">编辑素材</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-slate-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 表单 */}
        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <label className="block text-sm font-medium mb-1">商品ID</label>
            <input value={material.item_id} disabled className="input-ios w-full bg-gray-100 dark:bg-slate-700 cursor-not-allowed" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">商品标题</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="input-ios w-full" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">售价</label>
            <input
              type="number" step="0.01" min="0"
              value={price} onChange={(e) => setPrice(Number(e.target.value) || 0)}
              className="input-ios w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">商品描述</label>
            <textarea
              value={description} onChange={(e) => setDescription(e.target.value)}
              rows={3} className="input-ios w-full resize-y"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              商品图片 <span className="text-xs text-gray-400">（每行一个URL）</span>
            </label>
            <textarea
              value={images} onChange={(e) => setImages(e.target.value)}
              rows={3} className="input-ios w-full resize-y font-mono text-xs"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">推广链接</label>
            <input value={clickUrl} onChange={(e) => setClickUrl(e.target.value)} className="input-ios w-full font-mono text-xs" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">券二合一链接</label>
            <input value={couponUrl} onChange={(e) => setCouponUrl(e.target.value)} className="input-ios w-full font-mono text-xs" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">优惠券信息</label>
            <input value={couponInfo} onChange={(e) => setCouponInfo(e.target.value)} className="input-ios w-full" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">淘口令</label>
            <input value={tpwd} onChange={(e) => setTpwd(e.target.value)} className="input-ios w-full" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">短连接</label>
            <input value={shortUrl} onChange={(e) => setShortUrl(e.target.value)} className="input-ios w-full font-mono text-xs" />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-gray-200 dark:border-slate-700">
          <button onClick={onClose} className="btn-ios-secondary">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-ios-primary flex items-center gap-1.5">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  )
}
