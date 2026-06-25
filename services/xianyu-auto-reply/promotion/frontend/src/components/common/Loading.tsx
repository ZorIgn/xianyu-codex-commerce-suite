/**
 * 推广返佣系统 - 加载中组件
 *
 * 提供全屏加载遮罩和按钮加载动画
 */

/** 全屏加载遮罩 */
export function FullScreenLoading() {
  return (
    <div className="fixed inset-0 bg-white/80 dark:bg-slate-900/80 z-[200] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
        <p className="text-sm text-slate-500 dark:text-slate-400">加载中...</p>
      </div>
    </div>
  )
}

/** 按钮内加载动画 */
export function ButtonLoading() {
  return (
    <div className="flex items-center gap-2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
      <span>处理中...</span>
    </div>
  )
}

/** 页面加载旋转 */
export function PageLoading() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
    </div>
  )
}
