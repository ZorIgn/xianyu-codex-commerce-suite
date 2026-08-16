import {
  Boxes,
  ExternalLink,
  Github,
  MessageSquareText,
  PackageCheck,
  Radio,
  ShieldCheck,
} from 'lucide-react'

const MODULES = [
  {
    icon: MessageSquareText,
    title: '闲鱼管理端',
    description: '管理账号、聊天、商品、订单、卡券和自动回复。',
  },
  {
    icon: Radio,
    title: '消息与订单服务',
    description: '接收闲鱼实时事件，将付款、数量变化和买家确认传给履约中心。',
  },
  {
    icon: PackageCheck,
    title: '本地履约中心',
    description: '负责库存导入、按份出库、发货队列、激活队列和审计记录。',
  },
  {
    icon: ShieldCheck,
    title: '状态与幂等',
    description: '通过库存状态机和幂等键降低重复出库、重复发货和重复激活。',
  },
]

const FLOW = [
  '买家咨询与付款',
  '订单进入持久化发货队列',
  '按购买数量分配库存',
  '闲鱼发送交付内容',
  '买家确认后进入激活队列',
  '结果回写与审计',
]

export function About() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <header className="border-b border-slate-200 pb-5 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-300">
            <Boxes className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
              Xianyu Codex Commerce Suite
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              闲鱼消息、订单与本地库存履约的一体化系统
            </p>
          </div>
        </div>
      </header>

      <section>
        <h2 className="mb-3 text-base font-semibold text-slate-900 dark:text-white">系统组成</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {MODULES.map(({ icon: Icon, title, description }) => (
            <article key={title} className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-start gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" />
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-200 py-5 dark:border-slate-700">
        <h2 className="mb-3 text-base font-semibold text-slate-900 dark:text-white">履约流程</h2>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {FLOW.map((step, index) => (
            <li key={step} className="flex items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {index + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold text-slate-900 dark:text-white">项目链接</h2>
        <div className="flex flex-wrap gap-3">
          <a
            href="https://github.com/ZorIgn/xianyu-codex-commerce-suite"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            <Github className="h-4 w-4" />
            项目仓库
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <a
            href="https://github.com/zhinianboke/xianyu-auto-reply"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            上游闲鱼项目
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </section>
    </div>
  )
}
