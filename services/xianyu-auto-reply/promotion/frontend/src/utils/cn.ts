/**
 * 推广返佣系统 - 样式工具函数
 *
 * 组合clsx和tailwind-merge，支持条件合并Tailwind CSS类名
 */
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
