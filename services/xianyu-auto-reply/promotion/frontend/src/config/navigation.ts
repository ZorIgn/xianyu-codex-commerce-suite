/**
 * 推广返佣系统 - 导航菜单配置
 *
 * 定义侧边栏菜单项、管理员菜单项
 * 支持一级菜单和二级子菜单
 */
import { LayoutDashboard, Users, ShoppingBag, Search, ListChecks, Package, Send, Trash2, type LucideIcon } from 'lucide-react'

/** 子菜单项 */
export interface SubNavItem {
  key: string
  icon: LucideIcon
  label: string
  path: string
}

/** 导航菜单项（支持子菜单） */
export interface NavItem {
  key: string
  icon: LucideIcon
  label: string
  path: string
  adminOnly?: boolean
  children?: SubNavItem[]
}

/** 主菜单项 */
export const mainNavItems: NavItem[] = [
  { key: 'dashboard', icon: LayoutDashboard, label: '仪表盘', path: '/dashboard' },
  { key: 'accounts', icon: Users, label: '账号管理', path: '/accounts' },
  {
    key: 'taobao-alliance',
    icon: ShoppingBag,
    label: '淘宝联盟',
    path: '/taobao-alliance',
    children: [
      { key: 'product-search', icon: Search, label: '选品广场', path: '/taobao-alliance/product-search' },
      { key: 'product-rules', icon: ListChecks, label: '选品规则', path: '/taobao-alliance/product-rules' },
      { key: 'materials', icon: Package, label: '素材库', path: '/taobao-alliance/materials' },
      { key: 'publish-rules', icon: Send, label: '发布规则', path: '/taobao-alliance/publish-rules' },
      { key: 'delete-rules', icon: Trash2, label: '删除规则', path: '/taobao-alliance/delete-rules' },
    ],
  },
]

/** 管理员菜单项（预留） */
export const adminNavItems: NavItem[] = []

/**
 * 根据路径获取菜单标签（用于顶部标签栏）
 */
export function getMenuLabelByPath(path: string): string {
  const allItems = [...mainNavItems, ...adminNavItems]
  for (const item of allItems) {
    if (item.children) {
      const child = item.children.find((c) => path.startsWith(c.path))
      if (child) return `${item.label} / ${child.label}`
    }
    if (path.startsWith(item.path)) return item.label
  }
  return '未知页面'
}
