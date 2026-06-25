/**
 * 免责声明内容组件
 * 
 * 共享的免责声明内容，用于弹窗和页面
 */

export function DisclaimerContent() {
  return (
    <div className="space-y-6 text-slate-700 dark:text-slate-300">
      {/* 数据存储说明 */}
      <section>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          数据存储说明
        </h3>
        <p className="text-sm mb-3">
          本系统在运行过程中，为保障服务正常运行，会存储以下用户数据：
        </p>
        
        <div className="space-y-3 text-sm">
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
            <h4 className="font-medium text-slate-900 dark:text-white">1. 账号密码</h4>
            <ul className="mt-1 space-y-1 text-slate-600 dark:text-slate-400">
              <li>• 系统会保存用户的账号和密码信息</li>
              <li>• 用于自动登录和维持会话状态</li>
              <li>• 账号密码数据仅存储在本地服务器，不会上传至第三方</li>
            </ul>
          </div>
          
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
            <h4 className="font-medium text-slate-900 dark:text-white">2. Cookie 数据</h4>
            <ul className="mt-1 space-y-1 text-slate-600 dark:text-slate-400">
              <li>• 系统会保存用户的登录 Cookie 信息</li>
              <li>• 用于维持用户登录状态和自动化操作</li>
              <li>• Cookie 数据仅存储在本地服务器，不会上传至第三方</li>
            </ul>
          </div>
          
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
            <h4 className="font-medium text-slate-900 dark:text-white">3. 商品信息</h4>
            <ul className="mt-1 space-y-1 text-slate-600 dark:text-slate-400">
              <li>• 系统会保存用户发布的商品相关信息</li>
              <li>• 包括但不限于：商品标题、描述、价格、图片等</li>
              <li>• 用于商品管理和自动回复功能</li>
            </ul>
          </div>
          
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
            <h4 className="font-medium text-slate-900 dark:text-white">4. 卡券信息</h4>
            <ul className="mt-1 space-y-1 text-slate-600 dark:text-slate-400">
              <li>• 系统会保存用户配置的卡券/卡密信息</li>
              <li>• 用于自动发货和订单处理功能</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 用户须知 */}
      <section>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          用户须知
        </h3>
        <div className="space-y-2 text-sm">
          <p><strong>1. 数据安全：</strong>请妥善保管您的账号密码和服务器访问权限，因用户自身原因导致的数据泄露，本系统不承担责任。</p>
          <p><strong>2. 合规使用：</strong>用户应确保使用本系统的行为符合相关平台的用户协议和法律法规，因违规使用导致的账号封禁或其他损失，由用户自行承担。</p>
          <p><strong>3. 数据备份：</strong>建议用户定期备份重要数据，因系统故障、服务器问题、黑客攻击等导致的数据丢失，本系统不承担责任。</p>
          <p><strong>4. 服务中断：</strong>本系统不保证服务的持续性和稳定性，因系统维护、升级或不可抗力导致的服务中断，本系统不承担责任。</p>
          <p><strong>5. 第三方平台：</strong>本系统依赖第三方平台接口运行，因第三方平台政策变更、接口调整等导致的功能异常，本系统不承担责任。</p>
          <p><strong>6. 免费服务：</strong>本项目未收取任何费用，没有义务解答任何疑问，没有义务解决任何问题。</p>
          <p><strong>7. 安全声明：</strong>本人技术有限，不是专业安全人员，无法完全保证数据安全，请用户自行评估风险。</p>
        </div>
      </section>

      {/* 隐私保护承诺 */}
      <section>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          隐私保护承诺
        </h3>
        <ul className="space-y-1 text-sm">
          <li>• 所有用户数据仅用于本系统功能运行</li>
          <li>• 不会将用户数据出售或分享给第三方</li>
          <li>• 用户可随时自行删除其存储的数据</li>
        </ul>
      </section>
    </div>
  )
}
