import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { MessageSquare, User, Lock, Mail, KeyRound, Eye, EyeOff } from 'lucide-react'
import { AuthNavbar } from '@/components/common/AuthNavbar'
import { SafeHtml } from '@/components/common/SafeHtml'
import { getDefaultAuthFooterAdSettings, getDefaultLoginBrandingSettings } from '@/api/settings'
import { login, verifyToken, getRegistrationStatus, generateCaptcha, verifyCaptcha, sendVerificationCode, getLoginCaptchaStatus, getLoginBrandingSettings, getAuthFooterAdSettings, getInitialPasswordSetupStatus, setInitialAdminPassword } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/utils/cn'
import { ButtonLoading } from '@/components/common/Loading'
import { GeetestCaptcha, type GeetestResult } from '@/components/common/GeetestCaptcha'

type LoginType = 'username' | 'email-password' | 'email-code'
type PasswordSetupMode = 'initial' | null

export function Login() {
  const navigate = useNavigate()
  const { setAuth, isAuthenticated } = useAuthStore()
  const { addToast } = useUIStore()

  const [loginType, setLoginType] = useState<LoginType>('username')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [registrationEnabled, setRegistrationEnabled] = useState(true)
  const [passwordSetupMode, setPasswordSetupMode] = useState<PasswordSetupMode>(null)
  const [localResetRequired, setLocalResetRequired] = useState(false)
  const [setupUsername, setSetupUsername] = useState('admin')
  const [setupPassword, setSetupPassword] = useState('')
  const [setupPasswordConfirmation, setSetupPasswordConfirmation] = useState('')
  const [loginCaptchaEnabled, setLoginCaptchaEnabled] = useState<boolean | null>(null)
  const [loginBranding, setLoginBranding] = useState(() => getDefaultLoginBrandingSettings())
  const [authFooterAd, setAuthFooterAd] = useState(() => getDefaultAuthFooterAdSettings())

  // Form states
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [emailForCode, setEmailForCode] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')
  const [verificationCode, setVerificationCode] = useState('')

  // Captcha states
  const [captchaImage, setCaptchaImage] = useState('')
  const [sessionId] = useState(() => `session_${Math.random().toString(36).substr(2, 9)}_${Date.now()}`)
  const [captchaVerified, setCaptchaVerified] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [verifying, setVerifying] = useState(false)

  // 极验滑动验证码状态
  const [geetestResult, setGeetestResult] = useState<GeetestResult | null>(null)
  const [geetestKey, setGeetestKey] = useState(0)

  // 重置滑动验证码（登录失败时使用）
  const resetGeetest = () => {
    setGeetestResult(null)
    setGeetestKey((k) => k + 1)
  }

  // Check if already logged in
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard')
      return
    }

    const token = localStorage.getItem('auth_token')
    if (token) {
      verifyToken()
        .then((result) => {
          if (result.authenticated) {
            navigate('/dashboard')
          }
        })
        .catch(() => {
          localStorage.removeItem('auth_token')
        })
    }
  }, [isAuthenticated, navigate])

  // Load initial states
  useEffect(() => {
    getRegistrationStatus()
      .then((result) => setRegistrationEnabled(result.enabled))
      .catch(() => {})

    getInitialPasswordSetupStatus()
      .then((result) => {
        if (result.success && result.data?.requires_password_setup) {
          setSetupUsername(result.data.username || 'admin')
          setPasswordSetupMode('initial')
        }
      })
      .catch(() => {})

    getLoginCaptchaStatus()
      .then((result) => setLoginCaptchaEnabled(result.enabled))
      .catch(() => {})

    getLoginBrandingSettings()
      .then((result) => setLoginBranding(result))
      .catch(() => {})

    getAuthFooterAdSettings()
      .then((result) => setAuthFooterAd(result))
      .catch(() => {})
  }, [])

  // Load captcha when switching to email-code
  useEffect(() => {
    if (loginType === 'email-code') {
      loadCaptcha()
    }
  }, [loginType])

  // Countdown timer
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [countdown])

  // 自动验证图形验证码
  useEffect(() => {
    if (captchaCode.length === 4 && !captchaVerified && !verifying && loginType === 'email-code') {
      handleVerifyCaptchaAuto()
    }
  }, [captchaCode])

  const handleVerifyCaptchaAuto = async () => {
    if (captchaCode.length !== 4 || verifying) return
    setVerifying(true)
    try {
      const result = await verifyCaptcha(sessionId, captchaCode)
      if (result.success) {
        setCaptchaVerified(true)
        addToast({ type: 'success', message: '验证码验证成功' })
      } else {
        setCaptchaVerified(false)
        loadCaptcha()
        addToast({ type: 'error', message: '验证码错误' })
      }
    } catch {
      addToast({ type: 'error', message: '验证失败' })
    } finally {
      setVerifying(false)
    }
  }

  const loadCaptcha = async () => {
    try {
      const result = await generateCaptcha(sessionId)
      if (result.success && result.captcha_image) {
        setCaptchaImage(result.captcha_image)
        setCaptchaVerified(false)
        setCaptchaCode('')
      }
    } catch {
      addToast({ type: 'error', message: '加载验证码失败' })
    }
  }

  const handleSendCode = async () => {
    if (!captchaVerified || !emailForCode || countdown > 0) return

    try {
      const result = await sendVerificationCode(emailForCode, 'login', sessionId)
      if (result.success) {
        setCountdown(60)
        addToast({ type: 'success', message: '验证码已发送' })
      } else {
        addToast({ type: 'error', message: result.message || '发送失败' })
      }
    } catch {
      addToast({ type: 'error', message: '发送验证码失败' })
    }
  }

  // 切换登录类型时的处理
  const handleLoginTypeChange = (newType: LoginType) => {
    const oldType = loginType
    setLoginType(newType)
    
    // 只有在需要滑块验证的类型之间切换时，才重置验证结果
    // 用户名登录 <-> 邮箱密码登录：共用滑块，不需要重置
    // 切换到/从验证码登录：需要重置
    const needsGeetest = (type: LoginType) => type === 'username' || type === 'email-password'
    
    if (needsGeetest(oldType) !== needsGeetest(newType)) {
      // 从需要滑块切换到不需要，或反过来，重置状态
      setGeetestResult(null)
    } else if (needsGeetest(oldType) && needsGeetest(newType)) {
      // 在两个需要滑块的类型之间切换，保持验证结果
      // 不做任何操作
    }
  }

  // 极验验证成功回调
  const handleGeetestSuccess = (result: GeetestResult) => {
    setGeetestResult(result)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setLocalResetRequired(false)

    try {
      let loginData: any = {}

      if (loginType === 'username') {
        if (!username || !password) {
          addToast({ type: 'error', message: '请输入用户名和密码' })
          setLoading(false)
          return
        }
        // 检查滑动验证码（仅确认开启时前端校验）
        if (loginCaptchaEnabled === true && !geetestResult) {
          addToast({ type: 'error', message: '请完成滑动验证' })
          setLoading(false)
          return
        }
        loginData = { 
          username, 
          password,
          geetest_challenge: geetestResult?.challenge,
          geetest_validate: geetestResult?.validate,
          geetest_seccode: geetestResult?.seccode
        }
      } else if (loginType === 'email-password') {
        if (!email || !emailPassword) {
          addToast({ type: 'error', message: '请输入邮箱和密码' })
          setLoading(false)
          return
        }
        // 检查滑动验证码（仅确认开启时前端校验）
        if (loginCaptchaEnabled === true && !geetestResult) {
          addToast({ type: 'error', message: '请完成滑动验证' })
          setLoading(false)
          return
        }
        loginData = { 
          email, 
          password: emailPassword,
          geetest_challenge: geetestResult?.challenge,
          geetest_validate: geetestResult?.validate,
          geetest_seccode: geetestResult?.seccode
        }
      } else {
        if (!emailForCode || !verificationCode) {
          addToast({ type: 'error', message: '请输入邮箱和验证码' })
          setLoading(false)
          return
        }
        loginData = { email: emailForCode, verification_code: verificationCode }
      }

      const result = await login(loginData)

      if (result.success && result.token && result.refresh_token) {
        setAuth(result.token, result.refresh_token, {
          user_id: result.user_id!,
          username: result.username!,
          is_admin: result.is_admin!,
          account_limit: result.account_limit,
        })
        addToast({ type: 'success', message: '登录成功' })
        navigate('/dashboard')
      } else {
        if (result.requires_password_setup) {
          setLocalResetRequired(false)
          setSetupUsername(result.username || username || 'admin')
          setPasswordSetupMode('initial')
        } else if (result.requires_local_reset) {
          setLocalResetRequired(true)
          setPasswordSetupMode(null)
        }
        addToast({ type: 'error', message: result.message || '登录失败' })
        // 登录失败，重置滑动验证
        resetGeetest()
      }
    } catch {
      addToast({ type: 'error', message: '登录失败，请检查网络连接' })
      // 登录失败，重置滑动验证
      resetGeetest()
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordSetupSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!setupUsername.trim()) {
      addToast({ type: 'error', message: '请输入管理员用户名' })
      return
    }
    if (setupPassword.length < 6) {
      addToast({ type: 'error', message: '密码长度不能少于6位' })
      return
    }
    if (setupPassword !== setupPasswordConfirmation) {
      addToast({ type: 'error', message: '两次输入的密码不一致' })
      return
    }

    setLoading(true)
    try {
      const result = await setInitialAdminPassword({
        username: setupUsername.trim(),
        new_password: setupPassword,
      })

      if (result.success) {
        setLoginType('username')
        setUsername(setupUsername.trim())
        setPassword(setupPassword)
        setPasswordSetupMode(null)
        setSetupPassword('')
        setSetupPasswordConfirmation('')
        addToast({ type: 'success', message: result.message || '密码已更新，请使用新密码登录' })
      } else {
        addToast({ type: 'error', message: result.message || '密码更新失败' })
      }
    } catch {
      addToast({ type: 'error', message: '密码更新失败，请确认当前浏览器运行在部署机器本机' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 transition-colors duration-200">
      <AuthNavbar systemName={loginBranding['login.system_name']} />

      <div className="flex-1 flex pt-14">
      {/* Left side - Branding */}
      <motion.div 
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="hidden lg:flex lg:w-1/2 bg-slate-900 dark:bg-slate-950 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-transparent" />
        <div className="relative z-10 flex flex-col justify-center px-16">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="flex items-center gap-3 mb-8"
          >
            <div className="w-12 h-12 rounded-xl bg-blue-500 flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">{loginBranding['login.system_name']}</span>
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-4xl font-bold text-white mb-4 leading-tight whitespace-pre-line"
          >
            {loginBranding['login.system_title']}
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="text-slate-400 text-lg max-w-md"
          >
            {loginBranding['login.system_description']}
          </motion.p>
        </div>
        {/* Decorative circles */}
        <div className="absolute -bottom-32 -left-32 w-96 h-96 rounded-full bg-blue-600/10" />
        <div className="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-blue-600/5" />
      </motion.div>

      {/* Right side - Login form */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
        >
          {/* Mobile header */}
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="lg:hidden text-center mb-8"
          >
            <div className="w-12 h-12 rounded-xl bg-blue-500 text-white mx-auto mb-4 flex items-center justify-center">
              <MessageSquare className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">{loginBranding['login.system_name']}</h1>
          </motion.div>

          {/* Login Card */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-5 sm:p-8">
            <div className="mb-6">
              <h2 className="text-xl vben-card-title text-slate-900 dark:text-white">登录</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">欢迎回来，请登录您的账号</p>
            </div>

            {passwordSetupMode ? (
              <form onSubmit={handlePasswordSetupSubmit} className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    首次设置管理员密码
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                    这是新部署的管理员账号，请先设置密码。此操作仅允许在部署机器本机完成。
                  </p>
                </div>

                <div className="input-group">
                  <label className="input-label">管理员用户名</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={setupUsername}
                      onChange={(e) => setSetupUsername(e.target.value)}
                      placeholder="请输入管理员用户名"
                      className="input-ios pl-9"
                      autoComplete="username"
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label className="input-label">新密码</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={setupPassword}
                      onChange={(e) => setSetupPassword(e.target.value)}
                      placeholder="请输入新密码"
                      className="input-ios pl-9 pr-9"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      aria-label={showPassword ? '隐藏密码' : '显示密码'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="input-group">
                  <label className="input-label">确认新密码</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={setupPasswordConfirmation}
                      onChange={(e) => setSetupPasswordConfirmation(e.target.value)}
                      placeholder="请再次输入新密码"
                      className="input-ios pl-9"
                      autoComplete="new-password"
                    />
                  </div>
                </div>

                <button type="submit" disabled={loading} className="w-full btn-ios-primary">
                  {loading ? <ButtonLoading /> : '设置密码'}
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setPasswordSetupMode(null)}
                  className="w-full btn-ios-secondary"
                >
                  返回登录
                </button>
              </form>
            ) : (
              <>
            {/* Login type tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-700 mb-4 sm:mb-6 overflow-x-auto scrollbar-hide">
              {[
                { type: 'username' as const, label: '账号登录' },
                { type: 'email-password' as const, label: '邮箱密码' },
                { type: 'email-code' as const, label: '验证码' },
              ].map((tab) => (
                <button
                  key={tab.type}
                  onClick={() => handleLoginTypeChange(tab.type)}
                  className={cn(
                    'px-3 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap flex-shrink-0',
                    loginType === tab.type
                      ? 'text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400'
                      : 'text-slate-500 dark:text-slate-400 border-transparent hover:text-slate-700 dark:hover:text-slate-300'
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="space-y-3 sm:space-y-4">
              {/* Username login */}
              {loginType === 'username' && (
                <>
                  <div className="input-group">
                    <label className="input-label">用户名</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="请输入用户名"
                        className="input-ios pl-9"
                      />
                    </div>
                  </div>
                  <div className="input-group">
                    <label className="input-label">密码</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="请输入密码"
                        className="input-ios pl-9 pr-9"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* Email password login */}
              {loginType === 'email-password' && (
                <>
                  <div className="input-group">
                    <label className="input-label">邮箱地址</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@example.com"
                        className="input-ios pl-9"
                      />
                    </div>
                  </div>
                  <div className="input-group">
                    <label className="input-label">密码</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={emailPassword}
                        onChange={(e) => setEmailPassword(e.target.value)}
                        placeholder="请输入密码"
                        className="input-ios pl-9 pr-9"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* 滑动验证码 - 用户名和邮箱密码登录共用一个组件 */}
              {loginCaptchaEnabled === true && (loginType === 'username' || loginType === 'email-password') && (
                <div className="input-group">
                  <label className="input-label">滑动验证</label>
                  <GeetestCaptcha
                    key={geetestKey}
                    onSuccess={handleGeetestSuccess}
                    onError={(err) => addToast({ type: 'error', message: err })}
                    disabled={loading}
                  />
                </div>
              )}

              {/* Email code login */}
              {loginType === 'email-code' && (
                <>
                  <div className="input-group">
                    <label className="input-label">邮箱地址</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="email"
                        value={emailForCode}
                        onChange={(e) => setEmailForCode(e.target.value)}
                        placeholder="name@example.com"
                        className="input-ios pl-9"
                      />
                    </div>
                  </div>

                  {/* Captcha */}
                  <div className="input-group">
                    <label className="input-label">图形验证码</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={captchaCode}
                        onChange={(e) => setCaptchaCode(e.target.value)}
                        placeholder="输入验证码"
                        maxLength={4}
                        className="input-ios flex-1"
                        disabled={captchaVerified}
                      />
                      <img
                        src={captchaImage}
                        alt="验证码"
                        onClick={loadCaptcha}
                        className="h-[38px] rounded border border-gray-300 cursor-pointer hover:opacity-80 transition-opacity"
                      />
                    </div>
                    <p className={cn(
                      'text-xs',
                      captchaVerified ? 'text-green-600' : verifying ? 'text-blue-500' : 'text-gray-400'
                    )}>
                      {captchaVerified ? '✓ 验证成功' : verifying ? '验证中...' : '点击图片更换验证码'}
                    </p>
                  </div>

                  {/* Email code */}
                  <div className="input-group">
                    <label className="input-label">邮箱验证码</label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text"
                          value={verificationCode}
                          onChange={(e) => setVerificationCode(e.target.value)}
                          placeholder="6位数字验证码"
                          maxLength={6}
                          className="input-ios pl-9"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleSendCode}
                        disabled={!captchaVerified || !emailForCode || countdown > 0}
                        className="btn-ios-secondary whitespace-nowrap"
                      >
                        {countdown > 0 ? `${countdown}s` : '发送'}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full btn-ios-primary"
              >
                {loading ? <ButtonLoading /> : '登 录'}
              </button>
            </form>
              </>
            )}

            {localResetRequired && !passwordSetupMode && (
              <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                <p className="font-medium">管理员账号暂时无法登录</p>
                <p className="mt-1">
                  请在部署机器运行仓库根目录的本地 reset 脚本，交互输入新密码并解除锁定；完成后回到此页登录。
                </p>
                <code className="mt-2 block break-all rounded bg-amber-100 px-2 py-1 text-xs dark:bg-amber-900/40">
                  reset-admin-password.bat
                </code>
              </div>
            )}

            {/* Forgot password + Register links */}
            <div className="flex items-center justify-between mt-6 text-sm">
              <Link to="/forgot-password" className="text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400">
                忘记密码?
              </Link>
              {registrationEnabled && (
                <Link to="/register" className="text-blue-600 dark:text-blue-400 font-medium hover:text-blue-700 dark:hover:text-blue-300">
                  立即注册
                </Link>
              )}
            </div>

          </div>

          {/* Footer */}
          <SafeHtml
            html={authFooterAd['auth.footer_ad_html']}
            className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500"
          />
        </motion.div>
      </div>
      </div>
    </div>
  )
}
