/**
 * 选品规则 - 新建/编辑弹窗
 *
 * 功能：
 * 1. 商品类目下拉（参照选品广场）
 * 2. 商品关键词输入
 * 3. 排序规则下拉（参照选品广场）
 * 4. 每天条数输入
 * 5. 类目和关键词至少填一个校验
 */
import { useState, useEffect } from 'react'
import { X, Loader2 } from 'lucide-react'
import { createProductRule, updateProductRule } from '@/api/productRule'
import type { ProductRule, RuleCreateParams } from '@/api/productRule'
import { listXYAccounts } from '@/api/publishRule'
import type { XYAccountOption } from '@/api/publishRule'
import { useUIStore } from '@/store/uiStore'

/** 淘宝常用商品类目（与选品广场一致） */
const CATEGORY_OPTIONS = [
  { id: '', label: '不限类目' },
  { id: '16', label: '女装/女士精品' },
  { id: '30', label: '男装' },
  { id: '50006843', label: '女鞋' },
  { id: '50011740', label: '流行男鞋' },
  { id: '1625', label: '内衣/家居服' },
  { id: '50006842', label: '箱包皮具/女包/男包' },
  { id: '50010404', label: '服饰配件/帽子/围巾' },
  { id: '50012029', label: '运动鞋' },
  { id: '50010728', label: '运动/瑜伽/健身' },
  { id: '50013886', label: '户外/登山/旅行' },
  { id: '1512', label: '手机' },
  { id: '1101', label: '笔记本电脑' },
  { id: '11', label: '电脑硬件/显示器/周边' },
  { id: '50008090', label: '3C数码配件' },
  { id: '14', label: '数码相机/摄像机' },
  { id: '50022703', label: '大家电' },
  { id: '50012100', label: '生活电器' },
  { id: '50012082', label: '厨房电器' },
  { id: '50011972', label: '影音电器' },
  { id: '50002768', label: '个人护理/按摩器材' },
  { id: '1801', label: '美容护肤/美体/精油' },
  { id: '50010788', label: '彩妆/香水/美妆工具' },
  { id: '50023282', label: '美发护发/假发' },
  { id: '50011397', label: '珠宝/钻石/翡翠/黄金' },
  { id: '50005700', label: '品牌手表/流行手表' },
  { id: '28', label: '眼镜/瑞士军刀' },
  { id: '50002766', label: '零食/坚果/特产' },
  { id: '50016422', label: '粮油米面/调味品' },
  { id: '50026316', label: '茶/酒/冲饮' },
  { id: '50020275', label: '传统滋补营养品' },
  { id: '21', label: '居家日用/创意礼品' },
  { id: '50016349', label: '厨房/餐饮用具' },
  { id: '50016348', label: '清洁/卫浴/收纳' },
  { id: '50008163', label: '床上用品/布艺软饰' },
  { id: '50020808', label: '家居饰品' },
  { id: '50008164', label: '住宅家具' },
  { id: '50025705', label: '洗护清洁剂/纸品/香薰' },
  { id: '27', label: '家装主材' },
  { id: '50020485', label: '五金/工具' },
  { id: '35', label: '奶粉/辅食/营养品' },
  { id: '50008165', label: '童装/童鞋/亲子装' },
  { id: '25', label: '玩具/模型/动漫/益智' },
  { id: '50014812', label: '尿片/洗护/喂哺/推车' },
  { id: '33', label: '书籍/杂志/报纸' },
  { id: '29', label: '宠物/宠物食品及用品' },
  { id: '50017300', label: '乐器/吉他/钢琴' },
  { id: '50007216', label: '鲜花速递/绿植园艺' },
  { id: '26', label: '汽车用品/配件/改装' },
]

/** 排序选项（与选品广场一致） */
const SORT_OPTIONS = [
  { key: 'default', label: '默认排序' },
  { key: 'total_sales_des', label: '销量降序' },
  { key: 'total_sales_asc', label: '销量升序' },
  { key: 'tk_rate_des', label: '收入率降序' },
  { key: 'tk_rate_asc', label: '收入率升序' },
  { key: 'tk_total_sales_des', label: '累计推广降序' },
  { key: 'final_promotion_price_asc', label: '价格升序' },
  { key: 'final_promotion_price_des', label: '价格降序' },
]

interface Props {
  /** 编辑时传入已有规则，新建传null */
  rule: ProductRule | null
  /** 关闭弹窗 */
  onClose: () => void
  /** 保存成功后回调 */
  onSaved: () => void
}

/** 选品规则新建/编辑弹窗 */
export function ProductRuleFormModal({ rule, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const [saving, setSaving] = useState(false)

  const [ruleName, setRuleName] = useState('')
  const [accountId, setAccountId] = useState('')
  const [cat, setCat] = useState('')
  const [keyword, setKeyword] = useState('')
  const [sort, setSort] = useState('default')
  const [dailyCount, setDailyCount] = useState(10)
  const [remark, setRemark] = useState('')
  const [accounts, setAccounts] = useState<XYAccountOption[]>([])
  const [loadingAccounts, setLoadingAccounts] = useState(false)

  const isEdit = !!rule

  /** 编辑时回填 */
  useEffect(() => {
    if (rule) {
      setRuleName(rule.rule_name)
      setAccountId(rule.account_id)
      setCat(rule.cat)
      setKeyword(rule.keyword)
      setSort(rule.sort || 'default')
      setDailyCount(rule.daily_count)
      setRemark(rule.remark)
    }
  }, [rule])

  useEffect(() => {
    const fetchAccounts = async () => {
      setLoadingAccounts(true)
      try {
        const res = await listXYAccounts()
        if (res.success && res.data) {
          setAccounts(res.data)
          if (!rule?.account_id && !accountId && res.data.length > 0) {
            setAccountId(res.data[0].account_id)
          }
        } else {
          addToast({ type: 'error', message: res.message || '加载闲鱼账号失败' })
        }
      } catch {
        addToast({ type: 'error', message: '加载闲鱼账号失败' })
      } finally {
        setLoadingAccounts(false)
      }
    }
    fetchAccounts()
  }, [addToast, rule?.account_id])

  /** 获取类目名称 */
  const getCatName = (catId: string) => {
    const found = CATEGORY_OPTIONS.find((c) => c.id === catId)
    return found ? found.label : ''
  }

  /** 保存 */
  const handleSave = async () => {
    if (!accountId) {
      addToast({ type: 'warning', message: '请选择闲鱼账号' })
      return
    }

    if (!cat && !keyword.trim()) {
      addToast({ type: 'warning', message: '商品类目和关键词至少填写一项' })
      return
    }

    setSaving(true)
    try {
      const data: RuleCreateParams = {
        rule_name: ruleName.trim() || (keyword.trim() || getCatName(cat) || '未命名规则'),
        account_id: accountId,
        cat,
        cat_name: getCatName(cat),
        keyword: keyword.trim(),
        sort,
        daily_count: dailyCount,
        remark: remark.trim(),
      }

      const res = isEdit
        ? await updateProductRule(rule!.id, data)
        : await createProductRule(data)

      if (res.success) {
        addToast({ type: 'success', message: isEdit ? '规则已更新' : '规则已创建' })
        onSaved()
        onClose()
      } else {
        addToast({ type: 'error', message: res.message || '保存失败' })
      }
    } catch {
      addToast({ type: 'error', message: '保存请求失败' })
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
          <h2 className="text-base font-semibold">{isEdit ? '编辑选品规则' : '新建选品规则'}</h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-slate-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 表单 */}
        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* 规则名称 */}
          <div>
            <label className="block text-sm font-medium mb-1">规则名称</label>
            <input
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              placeholder="留空则自动取关键词或类目名"
              className="input-ios w-full"
            />
          </div>

          {/* 闲鱼账号 */}
          <div>
            <label className="block text-sm font-medium mb-1">闲鱼账号 <span className="text-red-500">*</span></label>
            {loadingAccounts ? (
              <div className="flex items-center gap-2 text-gray-400 text-sm py-2">
                <Loader2 className="w-4 h-4 animate-spin" />加载中...
              </div>
            ) : accounts.length === 0 ? (
              <p className="text-sm text-orange-500">暂无可用的闲鱼账号，请先在主系统中添加</p>
            ) : (
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="input-ios w-full"
              >
                <option value="">请选择账号</option>
                {accounts.map((opt) => (
                  <option key={opt.account_id} value={opt.account_id}>{opt.display_name}</option>
                ))}
              </select>
            )}
          </div>

          {/* 商品类目 */}
          <div>
            <label className="block text-sm font-medium mb-1">
              商品类目 <span className="text-xs text-gray-400">（与关键词至少填一项）</span>
            </label>
            <select
              value={cat}
              onChange={(e) => setCat(e.target.value)}
              className="input-ios w-full"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 商品关键词 */}
          <div>
            <label className="block text-sm font-medium mb-1">
              商品关键词 <span className="text-xs text-gray-400">（与类目至少填一项）</span>
            </label>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="如：蓝牙耳机、连衣裙"
              className="input-ios w-full"
            />
          </div>

          {/* 排序规则 */}
          <div>
            <label className="block text-sm font-medium mb-1">排序规则</label>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="input-ios w-full"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 每天条数 */}
          <div>
            <label className="block text-sm font-medium mb-1">每天选品条数</label>
            <input
              type="number"
              min={1}
              value={dailyCount}
              onChange={(e) => setDailyCount(Math.max(1, Number(e.target.value) || 1))}
              className="input-ios w-full"
            />
            <p className="text-xs text-gray-400 mt-1">最小值为 1，不限制上限</p>
          </div>

          {/* 备注 */}
          <div>
            <label className="block text-sm font-medium mb-1">备注</label>
            <input
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="选填"
              className="input-ios w-full"
            />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-gray-200 dark:border-slate-700">
          <button onClick={onClose} className="btn-ios-secondary">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-ios-primary flex items-center gap-1.5">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {isEdit ? '保存' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
