/**
 * 使用教程页面
 * 
 * 功能：
 * 1. 左侧显示菜单目录导航（按钮作为二级目录）
 * 2. 右侧显示详细的功能说明
 * 3. 点击左侧目录可快速跳转到对应内容
 */
import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { 
  BookOpen, 
  ChevronRight,
  ChevronDown,
  LayoutDashboard,
  Users,
  Package,
  ShoppingCart,
  MessageSquare,
  Bell,
  MessageCircle,
  Radar,
  Clock,
  Settings,
  UserCog,
  FileText,
  Shield,
  Info,
  AlertTriangle,
  Filter,
  MessageSquarePlus,
  Repeat,
  Megaphone,
  Star,
  Timer,
  ScrollText,
  Image,
  Circle,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// 教程内容数据结构
interface TutorialSection {
  id: string
  icon?: React.ElementType
  title: string
  description: string
  important?: boolean  // 重要提示，用红色标注
  children?: TutorialSection[]
}

// 教程内容数据 - 按钮作为children（不包含刷新、筛选、搜索类按钮）
const tutorialData: TutorialSection[] = [
  {
    id: 'dashboard',
    icon: LayoutDashboard,
    title: '仪表盘',
    description: '系统首页，展示账号统计、订单统计、关键词统计等核心数据概览。',
  },
  {
    id: 'accounts',
    icon: Users,
    title: '账号管理',
    description: '管理闲鱼账号，支持扫码登录、密码登录、手动输入Cookie等多种方式添加账号。',
    children: [
      { id: 'accounts-qrcode', title: '扫码登录', description: '使用闲鱼APP扫描二维码登录，触发人脸验证后无法处理，不推荐使用。' },
      { id: 'accounts-password', title: '账号密码', description: '使用闲鱼账号和密码登录，可能需要进行人脸验证。' },
      { id: 'accounts-manual', title: '手动输入', description: '手动输入Cookie信息添加账号，适合高级用户。填写账号密码后可自动续期。' },
      { id: 'accounts-enable', title: '启用/禁用', description: '切换账号的启用状态，禁用后不再自动回复。' },
      { id: 'accounts-ai', title: 'AI回复', description: '开启/关闭该账号的AI智能回复功能。' },
      { id: 'accounts-redelivery', title: '定时补发货', description: '开启后系统会定时检查未发货订单并自动发货。' },
      { id: 'accounts-rate', title: '定时补评价', description: '开启后系统会定时检查未评价订单并自动评价。' },
      { id: 'accounts-polish', title: '商品擦亮', description: '开启后系统会定时擦亮商品，提高曝光率。' },
      { id: 'accounts-auto-confirm', title: '自动确认发货', description: '开启后买家下单时自动调用闲鱼API确认发货，并发送虚拟商品/卡券内容。想要自动发货必须开启此功能。', important: true },
      { id: 'accounts-ai-settings', title: 'AI设置', description: '配置该账号的AI回复参数，包括AI模型、系统提示词等。' },
      { id: 'accounts-default-reply', title: '默认回复', description: '设置该账号的默认回复内容，当没有匹配到关键词且未开启AI时发送。' },
      { id: 'accounts-proxy', title: '代理设置', description: '配置该账号使用的网络代理，支持HTTP/SOCKS5代理。' },
      { id: 'accounts-msg-wait', title: '消息等待', description: '设置消息等待时间，在该时间内收到的多条消息会合并处理，避免频繁回复。' },
      { id: 'accounts-face', title: '人脸验证', description: '当账号需要人脸验证时，通过此功能完成验证流程。' },
      { id: 'accounts-confirm-msg', title: '确认收货消息', description: '设置买家确认收货后自动发送的消息内容，如好评引导语。' },
      { id: 'accounts-auto-rate', title: '自动评价', description: '配置自动评价的内容。收到评价请求消息时会自动评价买家，定时补评价也会使用此内容。' },
    ],
  },
  {
    id: 'online-chat',
    icon: MessageCircle,
    title: '在线聊天',
    description: '实时查看和管理与买家的聊天会话，支持手动回复消息。',
    children: [
      { id: 'chat-send', title: '发送消息', description: '在选中的会话中发送文字消息。' },
    ],
  },
  {
    id: 'items',
    icon: Package,
    title: '商品管理',
    description: '管理账号下的商品信息，配置发货规则、默认回复、AI提示词等。',
    children: [
      { id: 'items-fetch', title: '获取商品', description: '从闲鱼获取账号下的所有商品信息并保存到本地。' },
      { id: 'items-batch-reply', title: '新增默认回复', description: '批量为选中的商品设置默认回复内容。' },
      { id: 'items-batch-ai', title: '新增AI提示词', description: '批量为选中的商品设置AI回复的提示词。' },
      { id: 'items-delivery', title: '发货配置', description: '配置商品的自动发货规则，支持固定文字、批量数据、API接口、图片等多种卡券类型。' },
      { id: 'items-reply', title: '默认回复', description: '设置商品的默认回复内容，买家咨询时自动发送。' },
      { id: 'items-ai-prompt', title: 'AI提示词', description: '设置商品的AI回复提示词，让AI更了解商品特点。' },
      { id: 'items-spec-switch', title: '多规格开关', description: '开启后支持按规格匹配不同的发货内容。', important: true },
      { id: 'items-multi-switch', title: '多数量发货开关', description: '开启后支持按购买数量发送多份卡券。' },
    ],
  },
  {
    id: 'orders',
    icon: ShoppingCart,
    title: '订单管理',
    description: '查看和管理所有订单，支持手动发货、查看订单详情等操作。',
    children: [
      { id: 'orders-manual-delivery', title: '手动发货', description: '对待发货订单执行手动发货操作。' },
      { id: 'orders-detail', title: '查看详情', description: '查看订单的详细信息，包括收货地址、发货内容等。' },
    ],
  },
  {
    id: 'keywords',
    icon: MessageSquare,
    title: '自动回复',
    description: '配置关键词自动回复规则，当买家消息包含关键词时自动发送预设回复。',
    children: [
      { id: 'keywords-add', title: '添加关键词', description: '添加新的关键词回复规则。' },
      { id: 'keywords-batch', title: '批量添加', description: '批量导入多个关键词规则。' },
      { id: 'keywords-edit', title: '编辑', description: '修改关键词的触发词和回复内容。' },
      { id: 'keywords-delete', title: '删除', description: '删除关键词规则。' },
    ],
  },
  {
    id: 'message-filters',
    icon: Filter,
    title: '消息过滤',
    description: '配置消息过滤规则，符合规则的消息将被忽略不处理。',
    children: [
      { id: 'filters-add', title: '添加过滤词', description: '添加新的过滤规则。' },
      { id: 'filters-edit', title: '编辑', description: '修改过滤规则。' },
      { id: 'filters-delete', title: '删除', description: '删除过滤规则。' },
    ],
  },
  {
    id: 'risk-logs',
    icon: Shield,
    title: '风控日志',
    description: '查看账号风控拦截记录，普通用户可查看自己的账号日志，管理员可查看全部。',
  },
  {
    id: 'notification-channels',
    icon: Bell,
    title: '通知渠道',
    description: '配置消息通知渠道，支持企业微信、钉钉、飞书、Bark等多种推送方式。',
    children: [
      { id: 'channels-add', title: '添加渠道', description: '添加新的通知渠道配置。' },
      { id: 'channels-test', title: '测试', description: '发送测试消息验证渠道配置是否正确。' },
      { id: 'channels-edit', title: '编辑', description: '修改渠道配置。' },
      { id: 'channels-delete', title: '删除', description: '删除通知渠道。' },
      { id: 'channels-toggle', title: '启用/禁用', description: '切换渠道的启用状态。' },
    ],
  },
  {
    id: 'message-notifications',
    icon: MessageCircle,
    title: '消息通知',
    description: '配置哪些类型的消息需要推送通知，如新订单、新消息等。',
    children: [
      { id: 'notifications-add', title: '添加规则', description: '添加新的通知规则。' },
      { id: 'notifications-edit', title: '编辑', description: '修改通知规则。' },
      { id: 'notifications-delete', title: '删除', description: '删除通知规则。' },
      { id: 'notifications-toggle', title: '启用/禁用', description: '切换规则的启用状态。' },
    ],
  },
  {
    id: 'goofish-compass',
    icon: Radar,
    title: '数据罗盘',
    description: '（管理员功能）闲鱼数据分析工具，搜索和分析商品数据。',
    children: [
      { id: 'compass-export', title: '导出', description: '导出搜索结果。' },
    ],
  },
  {
    id: 'goofish-scheduled-crawler',
    icon: Clock,
    title: '定时采集',
    description: '（管理员功能）配置定时采集任务，自动采集闲鱼商品数据。',
    children: [
      { id: 'crawler-add', title: '添加任务', description: '创建新的定时采集任务。' },
      { id: 'crawler-run', title: '立即执行', description: '手动触发采集任务。' },
      { id: 'crawler-edit', title: '编辑', description: '修改任务配置。' },
      { id: 'crawler-delete', title: '删除', description: '删除采集任务。' },
      { id: 'crawler-toggle', title: '启用/禁用', description: '切换任务的启用状态。' },
    ],
  },
  {
    id: 'settings',
    icon: Settings,
    title: '系统设置',
    description: '配置系统参数，包括主题、语言、个人信息等。',
    children: [
      { id: 'settings-password', title: '修改密码', description: '修改当前账号的登录密码。' },
      { id: 'settings-theme', title: '主题切换', description: '切换系统的明暗主题。' },
    ],
  },
  {
    id: 'admin',
    icon: UserCog,
    title: '管理员功能',
    description: '系统管理员专属功能，包括用户管理、日志查看、定时任务等。',
    children: [
      {
        id: 'admin-users',
        icon: UserCog,
        title: '用户管理',
        description: '管理系统用户，包括创建用户、修改权限、重置密码等。',
        children: [
          { id: 'users-add', title: '添加用户', description: '创建新的系统用户。' },
          { id: 'users-edit', title: '编辑', description: '修改用户信息和权限。' },
          { id: 'users-reset-pwd', title: '重置密码', description: '重置用户的登录密码。' },
          { id: 'users-toggle', title: '启用/禁用', description: '切换用户的启用状态。' },
        ],
      },
      {
        id: 'admin-logs',
        icon: ScrollText,
        title: '日志管理',
        description: '查看系统运行日志，包括系统日志、补发货日志等。',
        children: [
          {
            id: 'admin-system-logs',
            icon: FileText,
            title: '系统日志',
            description: '查看系统运行日志，排查问题。',
          },
          {
            id: 'admin-redelivery-logs',
            icon: Repeat,
            title: '补发货日志',
            description: '查看定时补发货的执行记录。',
            children: [
              { id: 'redelivery-detail', title: '查看详情', description: '查看批次的详细发货记录。' },
            ],
          },
          {
            id: 'admin-rate-logs',
            icon: Star,
            title: '补评价日志',
            description: '查看定时补评价的执行记录。',
            children: [
              { id: 'rate-logs-detail', title: '查看详情', description: '查看批次的详细评价记录。' },
            ],
          },
          {
            id: 'admin-polish-logs',
            icon: Star,
            title: '擦亮日志',
            description: '查看商品擦亮的执行记录。',
            children: [
              { id: 'polish-logs-detail', title: '查看详情', description: '查看批次的详细擦亮记录。' },
            ],
          },
        ],
      },
      {
        id: 'admin-scheduled-tasks',
        icon: Timer,
        title: '定时任务',
        description: '查看和管理系统定时任务的执行状态。',
        children: [
          { id: 'tasks-run', title: '立即执行', description: '手动触发定时任务。' },
        ],
      },
      {
        id: 'admin-announcements',
        icon: Megaphone,
        title: '公告管理',
        description: '发布和管理系统公告。',
        children: [
          { id: 'announcements-add', title: '添加公告', description: '发布新的系统公告。' },
          { id: 'announcements-edit', title: '编辑', description: '修改公告内容。' },
          { id: 'announcements-delete', title: '删除', description: '删除公告。' },
          { id: 'announcements-toggle', title: '启用/禁用', description: '切换公告的显示状态。' },
        ],
      },
      {
        id: 'admin-ad-manage',
        icon: Image,
        title: '广告管理',
        description: '管理系统广告位和广告内容。',
        children: [
          { id: 'ad-add', title: '添加广告', description: '创建新的广告。' },
          { id: 'ad-edit', title: '编辑', description: '修改广告内容。' },
          { id: 'ad-delete', title: '删除', description: '删除广告。' },
          { id: 'ad-audit', title: '审核', description: '审核用户提交的广告申请。' },
        ],
      },
    ],
  },
  {
    id: 'other',
    icon: Info,
    title: '其他功能',
    description: '意见反馈、广告申请、免责声明、关于等辅助功能。',
    children: [
      {
        id: 'feedback',
        icon: MessageSquarePlus,
        title: '意见反馈',
        description: '提交使用过程中遇到的问题或建议。',
        children: [
          { id: 'feedback-submit', title: '提交反馈', description: '提交新的意见或建议。' },
        ],
      },
      {
        id: 'ad-apply',
        icon: Image,
        title: '广告申请',
        description: '申请在系统中投放广告。',
        children: [
          { id: 'ad-apply-submit', title: '提交申请', description: '提交广告投放申请。' },
        ],
      },
      {
        id: 'disclaimer',
        icon: AlertTriangle,
        title: '免责声明',
        description: '查看系统的免责声明和使用条款。',
      },
      {
        id: 'about',
        icon: Info,
        title: '关于',
        description: '查看系统版本信息和开发者信息。',
      },
    ],
  },
]

export function Tutorial() {
  const [activeSection, setActiveSection] = useState<string>('dashboard')
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['dashboard']))
  const contentRef = useRef<HTMLDivElement>(null)
  const sectionRefs = useRef<{ [key: string]: HTMLElement | null }>({})

  // 滚动到指定章节
  const scrollToSection = (sectionId: string) => {
    setActiveSection(sectionId)
    const element = sectionRefs.current[sectionId]
    if (element && contentRef.current) {
      const containerTop = contentRef.current.getBoundingClientRect().top
      const elementTop = element.getBoundingClientRect().top
      const offset = elementTop - containerTop + contentRef.current.scrollTop - 20
      contentRef.current.scrollTo({ top: offset, behavior: 'smooth' })
    }
  }

  // 切换展开/折叠
  const toggleExpand = (sectionId: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev)
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId)
      } else {
        newSet.add(sectionId)
      }
      return newSet
    })
  }

  // 监听滚动更新当前章节
  useEffect(() => {
    const container = contentRef.current
    if (!container) return

    const handleScroll = () => {
      const containerTop = container.getBoundingClientRect().top
      let currentSection = 'dashboard'
      
      Object.entries(sectionRefs.current).forEach(([id, element]) => {
        if (element) {
          const elementTop = element.getBoundingClientRect().top - containerTop
          if (elementTop <= 100) {
            currentSection = id
          }
        }
      })
      
      setActiveSection(currentSection)
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  // 渲染目录项
  const renderNavItem = (section: TutorialSection, level: number = 0) => {
    const Icon = section.icon || Circle
    const isActive = activeSection === section.id
    const hasChildren = section.children && section.children.length > 0
    const isExpanded = expandedSections.has(section.id)
    
    return (
      <div key={section.id}>
        <div className="flex items-center">
          {hasChildren && (
            <button
              onClick={() => toggleExpand(section.id)}
              className="p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3 text-slate-400" />
              ) : (
                <ChevronRight className="w-3 h-3 text-slate-400" />
              )}
            </button>
          )}
          <button
            onClick={() => scrollToSection(section.id)}
            className={cn(
              'flex items-center gap-2 flex-1 px-2 py-1.5 text-sm rounded-md transition-colors text-left',
              !hasChildren && 'ml-5',
              level > 0 && 'text-xs',
              isActive
                ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
            )}
          >
            <Icon className={cn('flex-shrink-0', level === 0 ? 'w-4 h-4' : 'w-3 h-3')} />
            <span className="truncate">{section.title}</span>
          </button>
        </div>
        {hasChildren && isExpanded && (
          <div className={cn('ml-4', level > 0 && 'ml-3')}>
            {section.children!.map(child => renderNavItem(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  // 渲染内容章节
  const renderContentSection = (section: TutorialSection, level: number = 0) => {
    const Icon = section.icon || Circle
    const HeadingTag = level === 0 ? 'h2' : level === 1 ? 'h3' : 'h4'
    const headingClass = level === 0 
      ? 'text-xl font-bold text-blue-600 dark:text-blue-400' 
      : level === 1 
        ? 'text-lg font-semibold text-emerald-600 dark:text-emerald-400' 
        : 'text-base font-medium text-slate-700 dark:text-slate-300'
    
    return (
      <div
        key={section.id}
        ref={el => { sectionRefs.current[section.id] = el }}
        className={cn('mb-6', level > 0 && 'ml-4')}
      >
        <HeadingTag className={cn('flex items-center gap-2 mb-2', headingClass, section.important && 'text-red-600 dark:text-red-400')}>
          <Icon className={cn(level === 0 ? 'w-5 h-5' : 'w-4 h-4')} />
          {section.title}
          {section.important && <span className="text-xs bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400 px-1.5 py-0.5 rounded">重要</span>}
        </HeadingTag>
        <p className={cn('mb-3 text-sm', section.important ? 'text-red-600 dark:text-red-400 font-medium' : 'text-slate-600 dark:text-slate-400')}>{section.description}</p>
        
        {section.children?.map(child => renderContentSection(child, level + 1))}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="page-header flex-between mb-4">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            使用教程
          </h1>
          <p className="page-description">详细了解系统各项功能的使用方法</p>
        </div>
      </div>

      {/* Content */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-1 flex gap-4 min-h-0"
      >
        {/* 左侧目录 */}
        <div className="w-72 flex-shrink-0 hidden lg:block">
          <div className="vben-card h-full overflow-hidden">
            <div className="vben-card-header">
              <h2 className="vben-card-title">目录</h2>
            </div>
            <div className="p-2 overflow-y-auto" style={{ height: 'calc(100% - 50px)' }}>
              {tutorialData.map(section => renderNavItem(section))}
            </div>
          </div>
        </div>

        {/* 右侧内容 */}
        <div className="flex-1 min-w-0">
          <div className="vben-card h-full overflow-hidden">
            <div
              ref={contentRef}
              className="p-6 overflow-y-auto"
              style={{ height: 'calc(100vh - 180px)' }}
            >
              {tutorialData.map(section => renderContentSection(section))}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}