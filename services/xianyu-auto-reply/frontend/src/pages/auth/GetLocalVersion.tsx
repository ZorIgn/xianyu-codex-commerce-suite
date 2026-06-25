/**
 * 获取本地版页面（公开页面，无需登录）
 *
 * 功能：
 * 1. 显示微信公众号二维码图片
 * 2. 提示用户关注公众号"执念商业"发送"获取本地版"获取最新本地版和使用教程
 * 3. 支持点击放大预览二维码图片
 */
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Monitor, X } from 'lucide-react'
import { getQrcodeUrl } from '@/api/settings'
import { AuthNavbar, PublicPageFooter } from '@/components/common/AuthNavbar'

export function GetLocalVersion() {
  const [qrcodeUrl, setQrcodeUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  // 加载微信公众号二维码
  useEffect(() => {
    setLoading(true)
    getQrcodeUrl('wechat_official')
      .then((res) => {
        if (res.success && res.data?.image_url) {
          setQrcodeUrl(res.data.image_url)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors duration-200">
      <AuthNavbar />


      {/* 主内容区 */}
      <div className="pt-20 pb-10 px-4 sm:px-6 flex items-start justify-center min-h-screen">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-lg"
        >
          {/* 页面标题 */}
          <div className="text-center mb-6">
            <div className="w-14 h-14 rounded-xl bg-purple-500 text-white mx-auto mb-4 flex items-center justify-center">
              <Monitor className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">获取本地版</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              扫码关注公众号，获取最新本地版客户端
            </p>
          </div>

          {/* 二维码卡片 */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-5 sm:p-8">
            <div className="flex flex-col items-center">
              {/* 二维码图片 */}
              <div
                className="w-[200px] h-[200px] overflow-hidden rounded-xl border-2 border-slate-200 dark:border-slate-600 cursor-pointer
                           transition-all duration-200 hover:scale-105 hover:shadow-lg hover:border-purple-400 dark:hover:border-purple-500"
                onClick={() => qrcodeUrl && setPreviewImage(qrcodeUrl)}
              >
                {loading ? (
                  <div className="w-full h-full flex items-center justify-center bg-slate-50 dark:bg-slate-700">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
                  </div>
                ) : qrcodeUrl ? (
                  <img
                    src={qrcodeUrl}
                    alt="微信公众号二维码"
                    className="w-full h-full object-cover object-center"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                      const parent = (e.target as HTMLImageElement).parentElement
                      if (parent) {
                        parent.innerHTML = '<p class="text-slate-400 dark:text-slate-500 py-20 text-sm text-center">二维码加载失败</p>'
                      }
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-slate-50 dark:bg-slate-700">
                    <p className="text-slate-400 dark:text-slate-500 text-sm">二维码未配置</p>
                  </div>
                )}
              </div>

              {/* 提示文字 */}
              <div className="mt-6 text-center space-y-3">
                <p className="text-base font-medium text-slate-900 dark:text-white">
                  微信公众号：<span className="text-purple-600 dark:text-purple-400">执念商业</span>
                </p>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-100 dark:border-purple-800 p-4">
                  <p className="text-sm text-purple-700 dark:text-purple-300">
                    关注微信公众号 <span className="font-bold">"执念商业"</span>
                  </p>
                  <p className="text-sm text-purple-700 dark:text-purple-300 mt-1">
                    发送 <span className="font-bold bg-purple-100 dark:bg-purple-800/50 px-1.5 py-0.5 rounded">"获取本地版"</span> 获取最新本地版和使用教程
                  </p>
                </div>
              </div>

              {/* 补充说明 */}
              <div className="mt-5 w-full">
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4 space-y-2">
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    <span className="font-medium text-slate-700 dark:text-slate-300">本地版特点：</span>
                    无需服务器，本地一键启动，适合个人使用
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    <span className="font-medium text-slate-700 dark:text-slate-300">获取方式：</span>
                    长按识别或扫描上方二维码关注公众号即可
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* 底部 */}
          <PublicPageFooter />
        </motion.div>
      </div>

      {/* 图片预览弹窗 */}
      {previewImage && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute -top-10 right-0 p-2 text-white hover:text-gray-300 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={previewImage}
              alt="预览"
              className="max-w-full max-h-[85vh] rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  )
}
