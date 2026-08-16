import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare, Moon, Sun } from 'lucide-react'

import { getLoginBrandingSettings } from '@/api/auth'
import { getDefaultLoginBrandingSettings, LOGIN_BRANDING_UPDATED_EVENT } from '@/api/settings'
import type { LoginBrandingSettings } from '@/types'
import { initializeThemeMode, toggleThemeMode } from '@/utils/theme'

interface AuthNavbarProps {
  systemName?: string
}

const DEFAULT_SYSTEM_NAME = getDefaultLoginBrandingSettings()['login.system_name']

export function usePublicSystemName(systemName?: string): string {
  const [resolvedSystemName, setResolvedSystemName] = useState(
    systemName?.trim() || DEFAULT_SYSTEM_NAME,
  )

  useEffect(() => {
    if (systemName?.trim()) {
      setResolvedSystemName(systemName.trim())
      return
    }

    let cancelled = false
    getLoginBrandingSettings()
      .then((settings) => {
        if (!cancelled) setResolvedSystemName(settings['login.system_name'])
      })
      .catch(() => {
        if (!cancelled) setResolvedSystemName(DEFAULT_SYSTEM_NAME)
      })

    const handleBrandingUpdated = (event: Event) => {
      const detail = (event as CustomEvent<LoginBrandingSettings>).detail
      setResolvedSystemName(detail?.['login.system_name']?.trim() || DEFAULT_SYSTEM_NAME)
    }
    window.addEventListener(LOGIN_BRANDING_UPDATED_EVENT, handleBrandingUpdated as EventListener)
    return () => {
      cancelled = true
      window.removeEventListener(LOGIN_BRANDING_UPDATED_EVENT, handleBrandingUpdated as EventListener)
    }
  }, [systemName])

  return resolvedSystemName
}

export function PublicPageFooter({ systemName }: AuthNavbarProps) {
  const resolvedSystemName = usePublicSystemName(systemName)
  return (
    <p className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500">
      &copy; {new Date().getFullYear()} {resolvedSystemName}
    </p>
  )
}

export function AuthNavbar({ systemName }: AuthNavbarProps) {
  const resolvedSystemName = usePublicSystemName(systemName)
  const [isDark, setIsDark] = useState(false)

  useEffect(() => setIsDark(initializeThemeMode() === 'dark'), [])

  const toggleTheme = () => {
    setIsDark(toggleThemeMode() === 'dark')
  }

  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/95">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/login" className="flex min-w-0 items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-500">
            <MessageSquare className="h-4 w-4 text-white" />
          </span>
          <span className="truncate text-sm font-bold text-slate-900 dark:text-white">
            {resolvedSystemName}
          </span>
        </Link>
        <button
          type="button"
          onClick={toggleTheme}
          className="rounded-md p-2 text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          title={isDark ? '切换到亮色模式' : '切换到暗色模式'}
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </nav>
  )
}
