/**
 * 随机地址表单弹窗
 *
 * 功能：
 * 1. 管理员新增随机地址
 * 2. 管理员编辑随机地址
 * 3. 配置账号范围、搜索关键词、期望文本和权重
 */
import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { createPublishAddress, updatePublishAddress, type PublishAddress } from '@/api/publishAddresses'
import { Loading } from '@/components/common/Loading'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/apiError'

interface PublishAddressFormModalProps {
  initial?: PublishAddress | null
  onClose: () => void
  onSaved: (address: PublishAddress, mode: 'create' | 'update') => void
}

interface PublishAddressFormState {
  address: string
}

const buildInitialState = (initial?: PublishAddress | null): PublishAddressFormState => ({
  address: initial?.address ?? initial?.search_keyword ?? '',
})

export function PublishAddressFormModal({ initial, onClose, onSaved }: PublishAddressFormModalProps) {
  const { addToast } = useUIStore()
  const isEditMode = Boolean(initial)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<PublishAddressFormState>(() => buildInitialState(initial))

  const handleSubmit = async () => {
    if (!form.address.trim()) {
      addToast({ type: 'warning', message: '请填写地址' })
      return
    }

    setSaving(true)
    try {
      const payload = {
        address: form.address.trim(),
      }
      const result = isEditMode && initial
        ? await updatePublishAddress(initial.id, payload)
        : await createPublishAddress(payload)

      if (!result.success || !result.data?.address) {
        addToast({ type: 'error', message: result.message || (isEditMode ? '保存随机地址失败' : '创建随机地址失败') })
        return
      }

      addToast({
        type: 'success',
        message: result.message || (isEditMode ? '随机地址保存成功' : '随机地址创建成功'),
      })
      onSaved(result.data.address, isEditMode ? 'update' : 'create')
    } catch (error) {
      addToast({ type: 'error', message: getApiErrorMessage(error, isEditMode ? '保存随机地址失败' : '创建随机地址失败') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      {saving && <Loading fullScreen text={isEditMode ? '正在保存随机地址...' : '正在创建随机地址...'} />}
      <div className="modal-content max-w-2xl">
        <div className="modal-header">
          <h2 className="modal-title">{isEditMode ? '编辑随机地址' : '新增随机地址'}</h2>
          <button className="modal-close" onClick={onClose} disabled={saving}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="modal-body">
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              <div className="input-group">
                <label className="input-label">地址 <span className="text-red-500">*</span></label>
                <input
                  className="input-ios"
                  placeholder="如：北京市朝阳区"
                  value={form.address}
                  onChange={(e) => setForm((prev) => ({ ...prev, address: e.target.value }))}
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  发布时会把这里的内容输入到闲鱼“宝贝所在地”搜索框。
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-ios-secondary" onClick={onClose} disabled={saving}>取消</button>
          <button className="btn-ios-primary" onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {isEditMode ? '保存修改' : '确认新增'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default PublishAddressFormModal
