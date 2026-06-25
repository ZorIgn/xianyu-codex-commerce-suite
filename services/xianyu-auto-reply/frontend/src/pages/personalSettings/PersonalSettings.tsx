/**
 * 涓汉璁剧疆椤甸潰
 * 
 * 鍔熻兘锛?
 * 1. 鏄剧ず鍜岀紪杈戜釜浜轰綑棰?
 * 2. 淇敼鐧诲綍瀵嗙爜
 * 3. 鍚庣画鍙墿灞曟洿澶氫釜浜鸿缃」
 */
import { useState, useEffect, useRef } from 'react'
import { User, RefreshCw, Wallet, Plus, Key, Link2, Copy, RotateCcw, Save, Package, X, ScrollText, ArrowUpFromLine, Upload, QrCode, Eye, EyeOff } from 'lucide-react'
import { getUserSetting, updateUserSetting, createCardSecretKey, changePassword, getDockCode, resetDockCode, getSecretKey, resetSecretKey, uploadPaymentQrcode, getSystemSettings } from '@/api/settings'
import { createWithdraw, getSettlementRecords, type SettlementRecord } from '@/api/payment'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { PageLoading, ButtonLoading } from '@/components/common/Loading'
import { ConfirmModal } from '@/components/common/ConfirmModal'
import { RechargeModal } from './RechargeModal'
import { FundFlowModal } from './FundFlowModal'

// 浣欓璁剧疆鐨?key
const BALANCE_KEY = 'balance'
const CONTACT_WECHAT_KEY = 'contact_wechat'
const CONTACT_QQ_KEY = 'contact_qq'
const REDELIVERY_TRIGGER_KEYWORD_KEY = 'redelivery_trigger_keyword'
const PAYMENT_QRCODE_KEY = 'payment_qrcode'
const PAYMENT_TYPE_KEY = 'payment_type'
// 瀵规帴鍗″瘑绉橀挜鐨?key锛堟寜鐢ㄦ埛瀛樺偍锛岀敤浜庛€屽垎閿€鍗″埜銆嶉〉闈㈠鎺ヤ笂娓稿崱鍒哥郴缁燂級
const CARD_SECRET_KEY = 'distribution.card_secret_key'

export function PersonalSettings() {
  const { addToast } = useUIStore()
  const { isAuthenticated, token, _hasHydrated, user, clearAuth } = useAuthStore()
  const [loading, setLoading] = useState(true)
  const [balance, setBalance] = useState('')
  const [showRecharge, setShowRecharge] = useState(false)
  const [showFundFlowModal, setShowFundFlowModal] = useState(false)
  const [showSettlementModal, setShowSettlementModal] = useState(false)
  const [settlementRecords, setSettlementRecords] = useState<SettlementRecord[]>([])
  const [settlementLoading, setSettlementLoading] = useState(false)
  const [settlementPage, setSettlementPage] = useState(1)
  const [settlementPageSize, setSettlementPageSize] = useState(20)
  const [settlementTotal, setSettlementTotal] = useState(0)
  const [settlementTotalPages, setSettlementTotalPages] = useState(0)
  const [withdrawing, setWithdrawing] = useState(false)
  const [showWithdrawModal, setShowWithdrawModal] = useState(false)
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [withdrawMinAmount, setWithdrawMinAmount] = useState('')  // 鏈€浣庢彁鐜伴噾棰?
  // 鏀舵鐮佺姸鎬?
  const [showQrcodeModal, setShowQrcodeModal] = useState(false)
  const [paymentQrcode, setPaymentQrcode] = useState('')
  const [paymentType, setPaymentType] = useState<'alipay' | 'wechat'>('alipay')
  const [uploadingQrcode, setUploadingQrcode] = useState(false)
  const qrcodeFileRef = useRef<HTMLInputElement>(null)

  // 瀵规帴鐮佺姸鎬?
  const [dockCode, setDockCode] = useState('')
  const [dockCodeLoading, setDockCodeLoading] = useState(false)
  const [resettingDockCode, setResettingDockCode] = useState(false)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)

  // 鍒嗛攢绉橀挜鐘舵€?
  const [secretKey, setSecretKey] = useState('')
  const [secretKeyLoading, setSecretKeyLoading] = useState(false)
  const [resettingSecretKey, setResettingSecretKey] = useState(false)
  const [secretKeyResetConfirmOpen, setSecretKeyResetConfirmOpen] = useState(false)

  // 瀵规帴鍗″瘑绉橀挜鐘舵€侊紙鐢ㄤ簬鍒嗛攢鍗″埜瀵规帴涓婃父绯荤粺锛?
  const [cardSecretKey, setCardSecretKey] = useState('')
  const [savingCardSecretKey, setSavingCardSecretKey] = useState(false)
  const [creatingCardSecretKey, setCreatingCardSecretKey] = useState(false)
  const [showCardSecretKey, setShowCardSecretKey] = useState(false)

  // 鑱旂郴鏂瑰紡鐘舵€?
  const [contactWechat, setContactWechat] = useState('')
  const [contactQQ, setContactQQ] = useState('')
  const [savingContact, setSavingContact] = useState(false)

  // 閲嶅彂璐цЕ鍙戝叧閿瓧鐘舵€?
  const [redeliveryKeyword, setRedeliveryKeyword] = useState('')
  const [savingRedeliveryKeyword, setSavingRedeliveryKeyword] = useState(false)

  // 瀵嗙爜淇敼鐘舵€?
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  // 鍔犺浇涓汉璁剧疆
  const loadSettings = async () => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    try {
      setLoading(true)
      const result = await getUserSetting(BALANCE_KEY)
      if (result.success && result.value !== undefined) {
        setBalance(result.value)
      } else {
        setBalance('0.00')
      }
      const qrcodeResult = await getUserSetting(PAYMENT_QRCODE_KEY)
      if (qrcodeResult.success && qrcodeResult.value) {
        setPaymentQrcode(qrcodeResult.value)
      }
      const typeResult = await getUserSetting(PAYMENT_TYPE_KEY)
      if (typeResult.success && typeResult.value) {
        setPaymentType(typeResult.value as 'alipay' | 'wechat')
      }
      // 鍔犺浇閲嶅彂璐цЕ鍙戝叧閿瓧
      const redeliveryResult = await getUserSetting(REDELIVERY_TRIGGER_KEYWORD_KEY)
      if (redeliveryResult.success && redeliveryResult.value !== undefined) {
        setRedeliveryKeyword(redeliveryResult.value)
      }
      // 鍔犺浇鑱旂郴鏂瑰紡
      const wechatResult = await getUserSetting(CONTACT_WECHAT_KEY)
      if (wechatResult.success && wechatResult.value !== undefined) {
        setContactWechat(wechatResult.value)
      }
      const qqResult = await getUserSetting(CONTACT_QQ_KEY)
      if (qqResult.success && qqResult.value !== undefined) {
        setContactQQ(qqResult.value)
      }
      // 鍔犺浇瀵规帴鍗″瘑绉橀挜
      const cardKeyResult = await getUserSetting(CARD_SECRET_KEY)
      if (cardKeyResult.success && cardKeyResult.value !== undefined) {
        setCardSecretKey(cardKeyResult.value)
      }
    } catch {
      setBalance('0.00')
    } finally {
      setLoading(false)
    }
  }

  // 鍔犺浇瀵规帴鐮?
  const loadDockCode = async () => {
    try {
      setDockCodeLoading(true)
      const result = await getDockCode()
      if (result.success && result.dock_code) {
        setDockCode(result.dock_code)
      }
    } catch {
      // 闈欓粯澶辫触
    } finally {
      setDockCodeLoading(false)
    }
  }

  // 閲嶇疆瀵规帴鐮?
  const handleResetDockCode = async () => {
    try {
      setResettingDockCode(true)
      const result = await resetDockCode()
      if (result.success) {
        addToast({ type: 'success', message: '瀵规帴鐮佸凡閲嶇疆' })
        await loadDockCode()
      } else {
        addToast({ type: 'error', message: result.message || '閲嶇疆澶辫触' })
      }
    } catch {
      addToast({ type: 'error', message: '閲嶇疆瀵规帴鐮佸け璐? })
    } finally {
      setResettingDockCode(false)
      setResetConfirmOpen(false)
    }
  }

  // 澶嶅埗瀵规帴鐮?
  const handleCopyDockCode = () => {
    if (!dockCode) return
    navigator.clipboard.writeText(dockCode).then(() => {
      addToast({ type: 'success', message: '瀵规帴鐮佸凡澶嶅埗鍒板壀璐存澘' })
    }).catch(() => {
      addToast({ type: 'error', message: '澶嶅埗澶辫触锛岃鎵嬪姩澶嶅埗' })
    })
  }

  // 鍔犺浇鍒嗛攢绉橀挜
  const loadSecretKey = async () => {
    try {
      setSecretKeyLoading(true)
      const result = await getSecretKey()
      if (result.success && result.secret_key) {
        setSecretKey(result.secret_key)
      }
    } catch {
      // 闈欓粯澶辫触
    } finally {
      setSecretKeyLoading(false)
    }
  }

  // 鏇存崲鍒嗛攢绉橀挜
  const handleResetSecretKey = async () => {
    try {
      setResettingSecretKey(true)
      const result = await resetSecretKey()
      if (result.success) {
        addToast({ type: 'success', message: '鍒嗛攢绉橀挜宸叉洿鎹? })
        if (result.data?.secret_key) {
          setSecretKey(result.data.secret_key)
        } else {
          await loadSecretKey()
        }
      } else {
        addToast({ type: 'error', message: result.message || '鏇存崲澶辫触' })
      }
    } catch {
      addToast({ type: 'error', message: '鏇存崲鍒嗛攢绉橀挜澶辫触' })
    } finally {
      setResettingSecretKey(false)
      setSecretKeyResetConfirmOpen(false)
    }
  }

  // 澶嶅埗鍒嗛攢绉橀挜
  const handleCopySecretKey = () => {
    if (!secretKey) return
    navigator.clipboard.writeText(secretKey).then(() => {
      addToast({ type: 'success', message: '鍒嗛攢绉橀挜宸插鍒跺埌鍓创鏉? })
    }).catch(() => {
      addToast({ type: 'error', message: '澶嶅埗澶辫触锛岃鎵嬪姩澶嶅埗' })
    })
  }

  // 淇濆瓨瀵规帴鍗″瘑绉橀挜
  const handleSaveCardSecretKey = async () => {
    try {
      setSavingCardSecretKey(true)
      const result = await updateUserSetting(CARD_SECRET_KEY, cardSecretKey.trim(), '瀵规帴鍗″瘑绉橀挜')
      if (result.success) {
        addToast({ type: 'success', message: '瀵规帴鍗″瘑绉橀挜宸蹭繚瀛? })
      } else {
        addToast({ type: 'error', message: result.message || '淇濆瓨澶辫触' })
      }
    } catch {
      addToast({ type: 'error', message: '淇濆瓨瀵规帴鍗″瘑绉橀挜澶辫触' })
    } finally {
      setSavingCardSecretKey(false)
    }
  }

  // 涓€閿垱寤哄鎺ュ崱瀵嗙閽ワ細璋冪敤澶栭儴瀵嗛挜鏈嶅姟鍒涘缓骞惰嚜鍔ㄤ繚瀛樺埌褰撳墠鐢ㄦ埛
  const handleCreateCardSecretKey = async () => {
    // 宸插瓨鍦ㄥ垯绂佹鍒涘缓锛屾彁绀鸿仈绯荤鐞嗗憳閲嶇疆
    if (cardSecretKey.trim()) {
      addToast({ type: 'warning', message: '瀵规帴鍗″瘑绉橀挜宸插瓨鍦紝濡傞渶閲嶆柊鍒涘缓璇疯仈绯荤鐞嗗憳閲嶇疆' })
      return
    }
    try {
      setCreatingCardSecretKey(true)
      const result = await createCardSecretKey()
      if (result.success && result.data?.key_value) {
        setCardSecretKey(result.data.key_value)
        addToast({ type: 'success', message: result.message || '瀵规帴鍗″瘑绉橀挜鍒涘缓鎴愬姛' })
      } else {
        addToast({ type: 'error', message: result.message || '鍒涘缓澶辫触' })
      }
    } finally {
      setCreatingCardSecretKey(false)
    }
  }

  const loadSettlementRecords = async (page: number = 1, pageSize: number = settlementPageSize) => {
    try {
      setSettlementLoading(true)
      const result = await getSettlementRecords(page, pageSize)
      if (result.success && result.data) {
        setSettlementRecords(result.data.list)
        setSettlementPage(result.data.page)
        setSettlementPageSize(result.data.page_size)
        setSettlementTotal(result.data.total)
        setSettlementTotalPages(result.data.total_pages)
      } else {
        setSettlementRecords([])
        addToast({ type: 'error', message: result.message || '鍔犺浇缁撶畻璁板綍澶辫触' })
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string; message?: string } }; message?: string }
      const errorMsg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || '鍔犺浇缁撶畻璁板綍澶辫触'
      addToast({ type: 'error', message: errorMsg })
      setSettlementRecords([])
    } finally {
      setSettlementLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
    loadDockCode()
    loadSecretKey()
  }, [_hasHydrated, isAuthenticated, token])

  // 淇濆瓨閲嶅彂璐цЕ鍙戝叧閿瓧
  const handleSaveRedeliveryKeyword = async () => {
    try {
      setSavingRedeliveryKeyword(true)
      const trimmed = redeliveryKeyword.trim()
      await updateUserSetting(REDELIVERY_TRIGGER_KEYWORD_KEY, trimmed, '閲嶅彂璐цЕ鍙戝叧閿瓧')
      setRedeliveryKeyword(trimmed)
      addToast({ type: 'success', message: '閲嶅彂璐цЕ鍙戝叧閿瓧淇濆瓨鎴愬姛' })
    } catch {
      addToast({ type: 'error', message: '淇濆瓨澶辫触' })
    } finally {
      setSavingRedeliveryKeyword(false)
    }
  }

  // 涓婁紶鏀舵鐮?
  const handleUploadQrcode = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setUploadingQrcode(true)
      const result = await uploadPaymentQrcode(file, paymentType)
      if (result.success && result.data?.image_url) {
        setPaymentQrcode(result.data.image_url)
        setShowQrcodeModal(false)
        addToast({ type: 'success', message: '鏀舵鐮佷笂浼犳垚鍔? })
      } else {
        addToast({ type: 'error', message: result.message || '涓婁紶澶辫触' })
      }
    } catch {
      addToast({ type: 'error', message: '涓婁紶澶辫触' })
    } finally {
      setUploadingQrcode(false)
      e.target.value = ''
    }
  }

  const handleWithdraw = async () => {
    if (!paymentQrcode) {
      addToast({ type: 'warning', message: '璇峰厛涓婁紶鏀舵鐮? })
      return
    }

    if (!withdrawAmount.trim()) {
      addToast({ type: 'warning', message: '璇疯緭鍏ユ彁鐜伴噾棰? })
      return
    }

    const currentBalance = Number(balance || '0')
    const amountValue = Number(withdrawAmount.trim())

    // 鏍￠獙鏈€浣庢彁鐜伴噾棰?
    if (withdrawMinAmount) {
      const minAmt = Number(withdrawMinAmount)
      if (minAmt > 0 && amountValue < minAmt) {
        addToast({ type: 'warning', message: `鎻愮幇閲戦涓嶈兘浣庝簬鏈€浣庢彁鐜伴噾棰?楼${minAmt}` })
        return
      }
    }

    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      addToast({ type: 'warning', message: '鎻愮幇閲戦蹇呴』澶т簬0' })
      return
    }

    if (amountValue > currentBalance) {
      addToast({ type: 'warning', message: '鎻愮幇閲戦涓嶈兘澶т簬褰撳墠浣欓' })
      return
    }

    try {
      setWithdrawing(true)
      const result = await createWithdraw(withdrawAmount.trim())
      if (result.success) {
        const nextBalance = result.data?.balance
        if (nextBalance !== undefined) {
          setBalance(nextBalance)
        } else {
          await loadSettings()
        }
        setWithdrawAmount('')
        setShowWithdrawModal(false)
        addToast({ type: 'success', message: result.message || '鎻愮幇鐢宠宸叉彁浜わ紝绛夊緟瀹℃牳' })
        await loadSettlementRecords(1, settlementPageSize)
        setShowSettlementModal(true)
      } else {
        addToast({ type: 'error', message: result.message || '鎻愮幇鐢宠澶辫触' })
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string; message?: string } }; message?: string }
      const errorMsg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || '鎻愮幇鐢宠澶辫触'
      addToast({ type: 'error', message: errorMsg })
    } finally {
      setWithdrawing(false)
    }
  }

  const openSettlementModal = async () => {
    setShowSettlementModal(true)
    await loadSettlementRecords(1, settlementPageSize)
  }

  // 淇濆瓨鑱旂郴鏂瑰紡
  const handleSaveContact = async () => {
    try {
      setSavingContact(true)
      await updateUserSetting(CONTACT_WECHAT_KEY, contactWechat, '寰俊鑱旂郴鏂瑰紡')
      await updateUserSetting(CONTACT_QQ_KEY, contactQQ, 'QQ鑱旂郴鏂瑰紡')
      addToast({ type: 'success', message: '鑱旂郴鏂瑰紡淇濆瓨鎴愬姛' })
    } catch {
      addToast({ type: 'error', message: '淇濆瓨鑱旂郴鏂瑰紡澶辫触' })
    } finally {
      setSavingContact(false)
    }
  }

  // 淇敼瀵嗙爜
  const handleChangePassword = async () => {
    if (!currentPassword) {
      addToast({ type: 'warning', message: '璇疯緭鍏ュ綋鍓嶅瘑鐮? })
      return
    }
    if (!newPassword) {
      addToast({ type: 'warning', message: '璇疯緭鍏ユ柊瀵嗙爜' })
      return
    }
    if (newPassword !== confirmPassword) {
      addToast({ type: 'warning', message: '涓ゆ杈撳叆鐨勫瘑鐮佷笉涓€鑷? })
      return
    }
    if (newPassword.length < 6) {
      addToast({ type: 'warning', message: '鏂板瘑鐮侀暱搴︿笉鑳藉皯浜?浣? })
      return
    }
    try {
      setChangingPassword(true)
      const result = await changePassword({ current_password: currentPassword, new_password: newPassword })
      if (result.success) {
        addToast({ type: 'success', message: '瀵嗙爜淇敼鎴愬姛锛屽嵆灏嗛€€鍑虹櫥褰? })
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
        // 寤惰繜1绉掑悗閫€鍑虹櫥褰?
        setTimeout(() => {
          clearAuth()
          window.location.href = '/login'
        }, 1000)
      } else {
        addToast({ type: 'error', message: result.message || '瀵嗙爜淇敼澶辫触' })
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string; message?: string } }; message?: string }
      const errorMsg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || '瀵嗙爜淇敼澶辫触'
      addToast({ type: 'error', message: errorMsg })
    } finally {
      setChangingPassword(false)
    }
  }

  if (loading) {
    return <PageLoading />
  }

  return (
    <div className="space-y-4">
      {/* 椤靛ご */}
      <div className="page-header flex-between flex-wrap gap-4">
        <div>
          <h1 className="page-title">涓汉璁剧疆</h1>
          <p className="page-description">绠＄悊涓汉璐︽埛淇℃伅鍜屽亸濂借缃?/p>
        </div>
        <button onClick={loadSettings} className="btn-ios-secondary">
          <RefreshCw className="w-4 h-4" />
          鍒锋柊
        </button>
      </div>

      {/* 璐︽埛淇℃伅 */}
      <div className="vben-card">
        <div className="vben-card-header">
          <h2 className="vben-card-title">
            <User className="w-4 h-4" />
            璐︽埛淇℃伅
          </h2>
        </div>
        <div className="vben-card-body space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="input-label">鐢ㄦ埛鍚?/label>
              <input
                type="text"
                value={user?.username || ''}
                disabled
                className="input-ios bg-gray-50 dark:bg-gray-800 cursor-not-allowed"
              />
            </div>
            <div>
              <label className="input-label">瑙掕壊</label>
              <input
                type="text"
                value={user?.is_admin ? '绠＄悊鍛? : '鏅€氱敤鎴?}
                disabled
                className="input-ios bg-gray-50 dark:bg-gray-800 cursor-not-allowed"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 浣欓绠＄悊 */}
      <div className="vben-card">
        <div className="vben-card-header flex items-center justify-between">
          <h2 className="vben-card-title">
            <Wallet className="w-4 h-4" />
            浣欓绠＄悊
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFundFlowModal(true)}
              className="btn-ios-secondary text-sm"
            >
              <Wallet className="w-4 h-4" />
              璧勯噾娴佹按
            </button>
            <button
              onClick={() => setShowQrcodeModal(true)}
              className="btn-ios-secondary text-sm"
            >
              <QrCode className="w-4 h-4" />
              鏀舵鐮佺鐞?
            </button>
            <button
              onClick={async () => {
                if (!paymentQrcode) {
                  addToast({ type: 'warning', message: '璇峰厛涓婁紶鏀舵鐮? })
                  return
                }
                // 鑾峰彇鏈€浣庢彁鐜伴噾棰?
                try {
                  const sysResult = await getSystemSettings()
                  if (sysResult.success && sysResult.data) {
                    setWithdrawMinAmount(sysResult.data['withdraw.min_amount'] || '')
                  }
                } catch { /* 鑾峰彇澶辫触涓嶉樆鏂祦绋?*/ }
                setWithdrawAmount('')
                setShowWithdrawModal(true)
              }}
              disabled={withdrawing}
              className="btn-ios-secondary text-sm"
            >
              {withdrawing ? <ButtonLoading /> : <ArrowUpFromLine className="w-4 h-4" />}
              鎻愮幇
            </button>
            <button
              onClick={openSettlementModal}
              className="btn-ios-secondary text-sm"
            >
              <ScrollText className="w-4 h-4" />
              缁撶畻璁板綍
            </button>
            <button
              onClick={() => setShowRecharge(true)}
              className="btn-ios-primary text-sm"
            >
              <Plus className="w-4 h-4" />
              浣欓鍏呭€?
            </button>
          </div>
        </div>
        <div className="vben-card-body space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="input-label">褰撳墠浣欓锛堝厓锛?/label>
              <div className="text-2xl font-semibold text-amber-600 dark:text-amber-400">
                楼{balance || '0.00'}
              </div>
              <p className="text-xs text-gray-500 mt-1">鐐瑰嚮"浣欓鍏呭€?鎸夐挳鍙€氳繃鏀粯瀹濇壂鐮佸厖鍊?/p>
            </div>
            <div>
              <label className="input-label">鏀舵鐮?/label>
              {paymentQrcode ? (
                <div className="flex items-center gap-2">
                  <img
                    src={paymentQrcode.startsWith('http') ? paymentQrcode : paymentQrcode}
                    alt="鏀舵鐮?
                    className="w-16 h-16 rounded-lg border border-slate-200 dark:border-slate-700 object-contain"
                  />
                  <span className="text-xs text-slate-500">{paymentType === 'wechat' ? '寰俊' : '鏀粯瀹?}鏀舵鐮?/span>
                </div>
              ) : (
                <div className="text-sm text-slate-500 dark:text-slate-400">鏈笂浼狅紝鐐瑰嚮銆屾敹娆剧爜绠＄悊銆嶄笂浼?/div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 鍒嗛攢绠＄悊 */}
      <div className="vben-card">
        <div className="vben-card-header">
          <h2 className="vben-card-title">
            <Link2 className="w-4 h-4" />
            鍒嗛攢绠＄悊
          </h2>
        </div>
        <div className="vben-card-body space-y-4">
          <div>
            <label className="input-label">瀵规帴鐮?/label>
            <p className="text-xs text-gray-500 mb-2">瀵规帴鐮佺敤浜庡垎閿€鍟嗚瘑鍒偍鐨勮韩浠斤紝鍒嗕韩缁欎笅绾у垎閿€鍟嗗嵆鍙鎺ユ偍鐨勫崱鍒?/p>
            <div className="flex items-center gap-3">
              {dockCodeLoading ? (
                <div className="text-sm text-gray-400">鍔犺浇涓?..</div>
              ) : (
                <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 font-mono text-lg tracking-widest font-semibold text-gray-900 dark:text-white select-all">
                  {dockCode || '-'}
                </div>
              )}
              <button
                onClick={handleCopyDockCode}
                disabled={!dockCode}
                className="btn-ios-secondary text-sm"
                title="澶嶅埗瀵规帴鐮?
              >
                <Copy className="w-4 h-4" />
                澶嶅埗
              </button>
              <button
                onClick={() => setResetConfirmOpen(true)}
                disabled={resettingDockCode}
                className="btn-ios-secondary text-sm text-amber-600 dark:text-amber-400"
                title="閲嶇疆瀵规帴鐮?
              >
                <RotateCcw className={`w-4 h-4 ${resettingDockCode ? 'animate-spin' : ''}`} />
                閲嶇疆
              </button>
            </div>
          </div>

          {/* 绉橀挜璁剧疆 */}
          <div>
            <label className="input-label">绉橀挜</label>
            <p className="text-xs text-gray-500 mb-2">鍒嗛攢绉橀挜涓?2浣嶉殢鏈哄瓧绗︼紝鍏ㄥ眬鍞竴锛岀敤浜庡垎閿€鎺ュ彛鐨勮韩浠芥牎楠屻€傝濡ュ杽淇濈锛屽彲闅忔椂鏇存崲銆?/p>
            <div className="flex items-center gap-3 flex-wrap">
              {secretKeyLoading ? (
                <div className="text-sm text-gray-400">鍔犺浇涓?..</div>
              ) : (
                <div className="flex items-center px-4 py-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 font-mono text-sm tracking-wider font-semibold text-gray-900 dark:text-white break-all select-all">
                  {secretKey || '-'}
                </div>
              )}
              <button
                onClick={handleCopySecretKey}
                disabled={!secretKey}
                className="btn-ios-secondary text-sm"
                title="澶嶅埗绉橀挜"
              >
                <Copy className="w-4 h-4" />
                澶嶅埗
              </button>
              <button
                onClick={() => setSecretKeyResetConfirmOpen(true)}
                disabled={resettingSecretKey}
                className="btn-ios-secondary text-sm text-amber-600 dark:text-amber-400"
                title="鏇存崲绉橀挜"
              >
                <RotateCcw className={`w-4 h-4 ${resettingSecretKey ? 'animate-spin' : ''}`} />
                鏇存崲
              </button>
            </div>
          </div>

          {/* 瀵规帴鍗″瘑绉橀挜璁剧疆 */}
          <div>
            <label className="input-label">瀵规帴鍗″瘑绉橀挜</label>
            <p className="text-xs text-gray-500 mb-2">鐢ㄤ簬銆屽垎閿€鍗″埜銆嶉〉闈㈠鎺ヤ笂娓稿崱鍒哥郴缁熺殑閴存潈绉橀挜锛岃濡ュ杽淇濈銆備慨鏀瑰悗鐐瑰嚮銆屼繚瀛樸€嶇敓鏁堛€?/p>
            <p className="text-xs text-gray-500 mb-2">绉橀挜璧勯噾娴佹按鍜屼綑棰濆厖鍊硷紝璇疯繘鍏?<a className="text-xs text-blue-600 dark:text-blue-400 mb-2" href="http://agent.zhinianboke.com" target='_BLANK'>agent.zhinianboke.com</a> 涓繘琛屾搷浣溿€?/p>
            <p className="text-xs text-blue-600 dark:text-blue-400 mb-2">濡傛湁鍏朵粬鐤戦棶鍙仈绯?QQ锛?31779708 寰俊锛歾hinian_znbk</p>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="relative flex-1 min-w-[260px]">
                <input
                  type="text"
                  value={cardSecretKey}
                  onChange={(e) => setCardSecretKey(e.target.value)}
                  placeholder="璇疯緭鍏ュ鎺ュ崱瀵嗙閽?
                  className="input-ios pr-10"
                  style={{ WebkitTextSecurity: showCardSecretKey ? 'none' : 'disc' } as React.CSSProperties}
                />
                <button
                  type="button"
                  onClick={() => setShowCardSecretKey(!showCardSecretKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                  title={showCardSecretKey ? '闅愯棌' : '鏄剧ず'}
                >
                  {showCardSecretKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <button
                onClick={handleCreateCardSecretKey}
                disabled={creatingCardSecretKey || !!cardSecretKey.trim()}
                className="btn-ios-secondary text-sm"
                title={cardSecretKey.trim() ? '绉橀挜宸插瓨鍦紝濡傞渶閲嶆柊鍒涘缓璇疯仈绯荤鐞嗗憳閲嶇疆' : '涓€閿垱寤哄鎺ュ崱瀵嗙閽?}
              >
                {creatingCardSecretKey ? <ButtonLoading /> : <Plus className="w-4 h-4" />}
                鍒涘缓
              </button>
              <button
                onClick={handleSaveCardSecretKey}
                disabled={savingCardSecretKey}
                className="btn-ios-primary text-sm"
                title="淇濆瓨瀵规帴鍗″瘑绉橀挜"
              >
                {savingCardSecretKey ? <ButtonLoading /> : <Save className="w-4 h-4" />}
                淇濆瓨
              </button>
            </div>
          </div>

          {/* 鑱旂郴鏂瑰紡 */}
          <div>
            <label className="input-label">鑱旂郴鏂瑰紡</label>
            <p className="text-xs text-gray-500 mb-2">璁剧疆鎮ㄧ殑寰俊鍜孮Q锛屾柟渚垮垎閿€鍟嗚仈绯绘偍</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="input-label">寰俊</label>
                <input
                  type="text"
                  value={contactWechat}
                  onChange={(e) => setContactWechat(e.target.value)}
                  placeholder="璇疯緭鍏ュ井淇″彿"
                  className="input-ios"
                />
              </div>
              <div>
                <label className="input-label">QQ</label>
                <input
                  type="text"
                  value={contactQQ}
                  onChange={(e) => setContactQQ(e.target.value)}
                  placeholder="璇疯緭鍏Q鍙?
                  className="input-ios"
                />
              </div>
            </div>
            <button
              onClick={handleSaveContact}
              disabled={savingContact}
              className="btn-ios-primary mt-3"
            >
              {savingContact ? <ButtonLoading /> : <Save className="w-4 h-4" />}
              淇濆瓨鑱旂郴鏂瑰紡
            </button>
          </div>
        </div>
      </div>

      {/* 閲嶅彂璐цЕ鍙戝叧閿瓧 */}
      <div className="vben-card">
        <div className="vben-card-header">
          <h2 className="vben-card-title">
            <Package className="w-4 h-4" />
            閲嶅彂璐цЕ鍙戝叧閿瓧
          </h2>
        </div>
        <div className="vben-card-body space-y-4">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            璁剧疆鍚庯紝鍦ㄩ棽楸艰亰澶╀腑鑷繁鍙戦€併€屽叧閿瓧+璁㈠崟鍙枫€嶅嵆鍙Е鍙戣嚜鍔ㄩ噸鏂板彂璐с€備緥濡傚叧閿瓧涓恒€岄噸鏂拌Е鍙戙€嶏紝鍙戦€併€?502144774044041438閲嶆柊瑙﹀彂銆嶅皢鎻愬彇璁㈠崟鍙峰苟鑷姩鍙戣揣銆?
            <br />
            <span className="text-amber-500 dark:text-amber-400">娉ㄦ剰锛氬叧閿瓧涓嶅寘鍚墠鍚庣┖鏍硷紱濡傛灉璁㈠崟涓嶅湪鏁版嵁搴撲腑锛岀郴缁熶細鑷姩鏍规嵁璁㈠崟鍙疯幏鍙栬鍗曚俊鎭悗鍐嶅彂璐с€?/span>
          </p>
          <div className="input-group">
            <label className="input-label">瑙﹀彂鍏抽敭瀛?/label>
            <input
              type="text"
              value={redeliveryKeyword}
              onChange={(e) => setRedeliveryKeyword(e.target.value)}
              placeholder="渚嬪锛氶噸鏂拌Е鍙?
              className="input-ios"
            />
            <p className="text-xs text-gray-400 mt-1">淇濆瓨鏃朵細鑷姩鍘婚櫎鍓嶅悗绌烘牸锛涚暀绌哄垯鍏抽棴姝ゅ姛鑳?/p>
          </div>
          <button
            onClick={handleSaveRedeliveryKeyword}
            disabled={savingRedeliveryKeyword}
            className="btn-ios-primary"
          >
            {savingRedeliveryKeyword ? <ButtonLoading /> : <Save className="w-4 h-4" />}
            淇濆瓨
          </button>
        </div>
      </div>

      {/* 淇敼瀵嗙爜 */}
      <div className="vben-card">
        <div className="vben-card-header">
          <h2 className="vben-card-title">
            <Key className="w-4 h-4" />
            淇敼瀵嗙爜
          </h2>
        </div>
        <div className="vben-card-body space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="input-group">
              <label className="input-label">褰撳墠瀵嗙爜</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="璇疯緭鍏ュ綋鍓嶅瘑鐮?
                className="input-ios"
              />
            </div>
            <div />
            <div className="input-group">
              <label className="input-label">鏂板瘑鐮?/label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="璇疯緭鍏ユ柊瀵嗙爜锛堣嚦灏?浣嶏級"
                className="input-ios"
              />
            </div>
            <div className="input-group">
              <label className="input-label">纭鏂板瘑鐮?/label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="璇峰啀娆¤緭鍏ユ柊瀵嗙爜"
                className="input-ios"
              />
            </div>
          </div>
          <button
            onClick={handleChangePassword}
            disabled={changingPassword}
            className="btn-ios-primary"
          >
            {changingPassword ? <ButtonLoading /> : <Key className="w-4 h-4" />}
            淇敼瀵嗙爜
          </button>
        </div>
      </div>

      {/* 閲嶇疆瀵规帴鐮佺‘璁ゅ脊绐?*/}
      <ConfirmModal
        isOpen={resetConfirmOpen}
        title="閲嶇疆瀵规帴鐮?
        message="纭畾瑕侀噸缃鎺ョ爜鍚楋紵閲嶇疆鍚庢棫瀵规帴鐮佸皢澶辨晥锛岃纭繚宸查€氱煡鐩稿叧鍒嗛攢鍟嗐€?
        confirmText="纭畾閲嶇疆"
        cancelText="鍙栨秷"
        type="warning"
        loading={resettingDockCode}
        onConfirm={handleResetDockCode}
        onCancel={() => setResetConfirmOpen(false)}
      />

      {/* 鏇存崲鍒嗛攢绉橀挜纭寮圭獥 */}
      <ConfirmModal
        isOpen={secretKeyResetConfirmOpen}
        title="鏇存崲绉橀挜"
        message="纭畾瑕佹洿鎹㈠垎閿€绉橀挜鍚楋紵鏇存崲鍚庡皢鐢熸垚鏂扮殑32浣嶇閽ワ紝鏃х閽ョ珛鍗冲け鏁堛€?
        confirmText="纭畾鏇存崲"
        cancelText="鍙栨秷"
        type="warning"
        loading={resettingSecretKey}
        onConfirm={handleResetSecretKey}
        onCancel={() => setSecretKeyResetConfirmOpen(false)}
      />

      {/* 缁撶畻璁板綍寮圭獥 */}
      {showSettlementModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="flex h-[80vh] w-full max-w-5xl flex-col rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">缁撶畻璁板綍</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">鎸夊疄闄呭垱寤烘椂闂村€掑簭鏄剧ず锛屾渶鏂扮敵璇锋帓鍦ㄦ渶鍓嶉潰</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => loadSettlementRecords(settlementPage, settlementPageSize)} className="btn-ios-secondary text-sm" disabled={settlementLoading}>
                  <RefreshCw className={`w-4 h-4 ${settlementLoading ? 'animate-spin' : ''}`} />
                  鍒锋柊
                </button>
                <button
                  onClick={() => setShowSettlementModal(false)}
                  className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="h-full overflow-auto">
                <table className="table-ios">
                  <thead>
                    <tr>
                      <th>璁板綍ID</th>
                      <th>鎻愮幇閲戦</th>
                      <th>鏀舵鏂瑰紡</th>
                      <th>鐘舵€?/th>
                      <th>鎷掔粷鍘熷洜</th>
                      <th>鍒涘缓鏃堕棿</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settlementLoading ? (
                      <tr>
                        <td colSpan={6}>
                          <div className="py-10 text-center text-sm text-slate-500">鍔犺浇涓?..</div>
                        </td>
                      </tr>
                    ) : settlementRecords.length === 0 ? (
                      <tr>
                        <td colSpan={6}>
                          <div className="py-10 text-center text-sm text-slate-500">鏆傛棤缁撶畻璁板綍</div>
                        </td>
                      </tr>
                    ) : (
                      settlementRecords.map((record) => (
                        <tr key={record.id}>
                          <td>{record.id}</td>
                          <td>楼{record.amount}</td>
                          <td>{record.payment_type === 'wechat' ? '寰俊' : record.payment_type === 'alipay' ? '鏀粯瀹? : (record.alipay_id ? '鏀粯瀹? : '-')}</td>
                          <td>
                            <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                              record.status === 'pending_review' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                              record.status === 'approved' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                              record.status === 'paid' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                              'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            }`}>
                              {record.status === 'pending_review' ? '寰呭鏍? : record.status === 'approved' ? '宸查€氳繃' : record.status === 'paid' ? '宸叉墦娆? : '宸叉嫆缁?}
                            </span>
                          </td>
                          <td className="max-w-[200px] truncate text-red-600 dark:text-red-400" title={record.reject_reason || ''}>
                            {record.reject_reason || '-'}
                          </td>
                          <td className="whitespace-nowrap">{record.created_at ? new Date(record.created_at).toLocaleString('zh-CN') : '-'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4 dark:border-slate-700">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span>姣忛〉</span>
                <select
                  value={settlementPageSize}
                  onChange={async (e) => {
                    const nextSize = Number(e.target.value)
                    setSettlementPageSize(nextSize)
                    await loadSettlementRecords(1, nextSize)
                  }}
                  className="input-ios w-auto py-1 px-2 text-sm"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
                <span>鏉★紝鍏?{settlementTotal} 鏉?/span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => loadSettlementRecords(settlementPage - 1, settlementPageSize)}
                  disabled={settlementPage <= 1 || settlementLoading}
                  className="btn-ios-secondary btn-sm"
                >
                  涓婁竴椤?
                </button>
                <span className="px-3 text-sm text-gray-600 dark:text-gray-400">
                  {settlementPage} / {settlementTotalPages || 1}
                </span>
                <button
                  onClick={() => loadSettlementRecords(settlementPage + 1, settlementPageSize)}
                  disabled={settlementPage >= settlementTotalPages || settlementLoading || settlementTotalPages === 0}
                  className="btn-ios-secondary btn-sm"
                >
                  涓嬩竴椤?
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 鎻愮幇寮圭獥 */}
      {showWithdrawModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">鐢宠鎻愮幇</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">鎻愮幇鍚庡皢绔嬪嵆鎵ｅ噺浣欓锛屽苟鐢熸垚寰呭鏍哥粨绠楄褰?/p>
              </div>
              <button
                onClick={() => {
                  if (withdrawing) return
                  setShowWithdrawModal(false)
                }}
                className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                <div>褰撳墠浣欓锛毬balance || '0.00'}</div>
                <div className="mt-1">
                  鏀舵鏂瑰紡锛歿paymentQrcode ? (paymentType === 'wechat' ? '寰俊' : '鏀粯瀹?) + '鏀舵鐮? : '鏈笂浼犳敹娆剧爜'}
                </div>
                {withdrawMinAmount && Number(withdrawMinAmount) > 0 && (
                  <div className="mt-1 text-amber-600 dark:text-amber-400">
                    鏈€浣庢彁鐜伴噾棰濓細楼{withdrawMinAmount}
                  </div>
                )}
              </div>
              <div>
                <label className="input-label">鎻愮幇閲戦锛堝厓锛?/label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={withdrawAmount}
                  onChange={(e) => setWithdrawAmount(e.target.value)}
                  placeholder="璇疯緭鍏ユ彁鐜伴噾棰?
                  className="input-ios"
                  autoFocus
                />
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                鎻愮幇鎻愪氦鍚庝細鍚屾鎵ｅ噺浣欓銆佸啓鍏ヨ祫閲戞祦姘达紝骞剁敓鎴愮姸鎬佷负鈥滃緟瀹℃牳鈥濈殑缁撶畻璁板綍銆?
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowWithdrawModal(false)}
                  className="btn-ios-secondary"
                  disabled={withdrawing}
                >
                  鍙栨秷
                </button>
                <button
                  onClick={handleWithdraw}
                  className="btn-ios-primary"
                  disabled={withdrawing}
                >
                  {withdrawing ? <ButtonLoading /> : <ArrowUpFromLine className="w-4 h-4" />}
                  纭鎻愮幇
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 鏀舵鐮佺鐞嗗脊绐?*/}
      {showQrcodeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">鏀舵鐮佺鐞?/h3>
              <button
                onClick={() => setShowQrcodeModal(false)}
                className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              {/* 鏀舵绫诲瀷閫夋嫨 */}
              <div>
                <label className="input-label">鏀舵鏂瑰紡</label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setPaymentType('alipay')}
                    className={`flex-1 rounded-xl border-2 py-3 text-sm font-medium transition ${
                      paymentType === 'alipay'
                        ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                        : 'border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-400'
                    }`}
                  >
                    鏀粯瀹?
                  </button>
                  <button
                    onClick={() => setPaymentType('wechat')}
                    className={`flex-1 rounded-xl border-2 py-3 text-sm font-medium transition ${
                      paymentType === 'wechat'
                        ? 'border-green-500 bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                        : 'border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-400'
                    }`}
                  >
                    寰俊
                  </button>
                </div>
              </div>
              {/* 褰撳墠鏀舵鐮侀瑙?*/}
              {paymentQrcode && (
                <div className="text-center">
                  <label className="input-label">褰撳墠鏀舵鐮?/label>
                  <img
                    src={paymentQrcode}
                    alt="褰撳墠鏀舵鐮?
                    className="mx-auto mt-2 h-40 w-40 rounded-xl border border-slate-200 object-contain dark:border-slate-700"
                  />
                </div>
              )}
              {/* 涓婁紶鍖哄煙 */}
              <div>
                <label className="input-label">{paymentQrcode ? '鏇存崲鏀舵鐮? : '涓婁紶鏀舵鐮?}</label>
                <div
                  onClick={() => qrcodeFileRef.current?.click()}
                  className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 py-8 transition hover:border-blue-400 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-800"
                >
                  {uploadingQrcode ? (
                    <ButtonLoading />
                  ) : (
                    <>
                      <Upload className="mb-2 h-8 w-8 text-slate-400" />
                      <span className="text-sm text-slate-500">鐐瑰嚮閫夋嫨鍥剧墖锛圝PG/PNG/WEBP锛?/span>
                    </>
                  )}
                </div>
                <input
                  ref={qrcodeFileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={handleUploadQrcode}
                />
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                璇蜂笂浼爗paymentType === 'wechat' ? '寰俊' : '鏀粯瀹?}鏀舵鐮佸浘鐗囷紝绠＄悊鍛樻墦娆炬椂灏嗙湅鍒版鏀舵鐮併€傚凡涓婁紶鐨勬敹娆剧爜鍙噸鏂颁笂浼犳浛鎹€?
              </div>
              <div className="flex justify-end">
                <button onClick={() => setShowQrcodeModal(false)} className="btn-ios-secondary">
                  鍏抽棴
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 璧勯噾娴佹按寮圭獥 */}
      <FundFlowModal
        visible={showFundFlowModal}
        onClose={() => setShowFundFlowModal(false)}
      />

      {/* 鍏呭€煎脊绐?*/}
      <RechargeModal
        visible={showRecharge}
        onClose={() => setShowRecharge(false)}
        onSuccess={loadSettings}
      />
    </div>
  )
}
