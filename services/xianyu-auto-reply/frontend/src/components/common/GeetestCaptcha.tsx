/**
 * 极验滑动验证码组件
 *
 * 功能：
 * 1. 初始化极验验证码
 * 2. 用户完成滑动后进行二次验证
 * 3. 验证成功后回调父组件
 *
 * 注意：极验的 challenge 是一次性的，每次初始化都需要重新获取
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { getGeetestRegister, geetestValidate } from '@/api/auth'

// 极验验证结果类型
export interface GeetestResult {
  challenge: string
  validate: string
  seccode: string
}

interface GeetestCaptchaProps {
  onSuccess: (result: GeetestResult) => void
  onError?: (error: string) => void
  disabled?: boolean
  buttonText?: string
  className?: string
}

declare global {
  interface Window {
    initGeetest?: (config: any, callback: (captchaObj: any) => void) => void
  }
}

// 全局缓存：极验SDK加载状态（SDK只需加载一次）
let geetestScriptLoaded = false
let geetestScriptLoading: Promise<void> | null = null

export function GeetestCaptcha({
  onSuccess,
  onError,
  disabled = false,
  buttonText = '点击进行验证',
  className = ''
}: GeetestCaptchaProps) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'verified' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')
  const captchaObjRef = useRef<any>(null)
  const initedRef = useRef(false)
  const mountedRef = useRef(true)
  const onSuccessRef = useRef(onSuccess)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onSuccessRef.current = onSuccess
    onErrorRef.current = onError
  }, [onSuccess, onError])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  // 加载极验JS SDK（带全局缓存，SDK只需加载一次）
  const loadScript = useCallback((): Promise<void> => {
    // 已加载完成
    if (geetestScriptLoaded && window.initGeetest) {
      return Promise.resolve()
    }

    // 正在加载中，等待
    if (geetestScriptLoading) {
      return geetestScriptLoading
    }

    // 开始加载
    geetestScriptLoading = new Promise<void>((resolve, reject) => {
      if (window.initGeetest) {
        geetestScriptLoaded = true
        resolve()
        return
      }

      const existing = document.querySelector('script[src*="geetest.com"]')
      if (existing) {
        const check = setInterval(() => {
          if (window.initGeetest) {
            clearInterval(check)
            geetestScriptLoaded = true
            resolve()
          }
        }, 100)
        setTimeout(() => {
          clearInterval(check)
          if (window.initGeetest) {
            geetestScriptLoaded = true
            resolve()
          } else {
            reject(new Error('加载超时'))
          }
        }, 10000)
        return
      }

      const script = document.createElement('script')
      script.src = 'https://static.geetest.com/static/tools/gt.js'
      script.async = true
      script.onload = () => {
        const check = setInterval(() => {
          if (window.initGeetest) {
            clearInterval(check)
            geetestScriptLoaded = true
            resolve()
          }
        }, 50)
        setTimeout(() => {
          clearInterval(check)
          if (window.initGeetest) {
            geetestScriptLoaded = true
            resolve()
          } else {
            reject(new Error('SDK初始化失败'))
          }
        }, 5000)
      }
      script.onerror = () => reject(new Error('脚本加载失败'))
      document.head.appendChild(script)
    }).finally(() => {
      geetestScriptLoading = null
    })

    return geetestScriptLoading
  }, [])

  // 初始化
  const init = useCallback(async () => {
    if (initedRef.current) return
    initedRef.current = true

    try {
      setStatus('loading')
      setErrorMsg('')

      await loadScript()

      // 每次初始化都需要获取新的 challenge（challenge 是一次性的）
      const res = await getGeetestRegister()
      if (!mountedRef.current) return

      if (!res.success || !res.data) {
        throw new Error(res.message || '获取参数失败')
      }

      const { gt, challenge, success, new_captcha } = res.data
      if (!gt || !challenge) {
        throw new Error('参数不完整')
      }

      window.initGeetest?.(
        {
          gt,
          challenge,
          offline: success === 0,
          new_captcha,
          product: 'bind',
          width: '100%',
          lang: 'zh-cn'
        },
        (obj: any) => {
          if (!mountedRef.current) return
          captchaObjRef.current = obj

          obj.onReady(() => {
            if (mountedRef.current) setStatus('ready')
          })

          obj.onSuccess(async () => {
            const result = obj.getValidate()
            if (!result) return

            // 显示验证中状态
            if (mountedRef.current) setStatus('loading')

            try {
              const validateRes = await geetestValidate({
                challenge: result.geetest_challenge,
                validate: result.geetest_validate,
                seccode: result.geetest_seccode
              })

              if (!mountedRef.current) return

              if (validateRes.success) {
                setStatus('verified')
                onSuccessRef.current({
                  challenge: result.geetest_challenge,
                  validate: result.geetest_validate,
                  seccode: result.geetest_seccode
                })
              } else {
                setErrorMsg(validateRes.message || '验证失败')
                setStatus('error')
                onErrorRef.current?.(validateRes.message || '验证失败')
                obj.reset()
              }
            } catch (err: any) {
              if (!mountedRef.current) return
              // 网络错误或超时，提示用户重试
              const errorMsg = err.message?.includes('timeout') ? '验证超时，请重试' : '验证异常，请重试'
              setErrorMsg(errorMsg)
              setStatus('error')
              onErrorRef.current?.(errorMsg)
              obj.reset()
            }
          })

          obj.onError(() => {
            if (mountedRef.current) {
              setErrorMsg('加载失败')
              setStatus('error')
              onErrorRef.current?.('加载失败')
            }
          })

          obj.onClose(() => {
            // 用户关闭，不处理
          })
        }
      )
    } catch (err: any) {
      initedRef.current = false
      if (mountedRef.current) {
        setErrorMsg(err.message || '初始化失败')
        setStatus('error')
        onErrorRef.current?.(err.message || '初始化失败')
      }
    }
  }, [loadScript])

  useEffect(() => {
    init()
    return () => {
      captchaObjRef.current = null
      initedRef.current = false
    }
  }, [init])

  const handleClick = () => {
    if (disabled) return

    if (status === 'error') {
      // 重试
      initedRef.current = false
      init()
      return
    }

    if (status === 'ready' && captchaObjRef.current) {
      captchaObjRef.current.verify()
    }
  }

  const btnClass = `w-full h-10 px-4 rounded-lg border transition-all duration-200 text-sm font-medium
    ${
      status === 'verified'
        ? 'bg-green-50 border-green-300 text-green-700 dark:bg-green-900/20 dark:border-green-700 dark:text-green-400'
        : status === 'error'
          ? 'bg-red-50 border-red-300 text-red-700 dark:bg-red-900/20 dark:border-red-700 dark:text-red-400 cursor-pointer'
          : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100 dark:bg-slate-800 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700'
    }
    ${disabled || status === 'loading' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`

  return (
    <div className={className}>
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || status === 'loading'}
        className={btnClass}
      >
        {status === 'loading' && (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            加载中...
          </span>
        )}
        {status === 'ready' && buttonText}
        {status === 'verified' && (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            验证成功
          </span>
        )}
        {status === 'error' && `${errorMsg}，点击重试`}
      </button>
    </div>
  )
}

/**
 * 清除极验缓存（已废弃，challenge不再缓存）
 * @deprecated challenge 是一次性的，不再缓存
 */
export const clearGeetestCache = () => {
  // 保留函数以兼容现有调用，但不再有实际作用
}

export default GeetestCaptcha
