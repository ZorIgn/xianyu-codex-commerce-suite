import { useMemo } from 'react'
import { cn } from '@/utils/cn'

const ALLOWED_TAGS = new Set(['a', 'b', 'br', 'div', 'em', 'i', 'p', 'small', 'span', 'strong', 'u'])
const STRIP_CONTENT_TAGS = new Set(['button', 'embed', 'form', 'iframe', 'input', 'object', 'script', 'select', 'style', 'textarea'])
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])
const ALLOWED_ATTRIBUTES: Record<string, Set<string>> = {
  a: new Set(['href', 'target', 'title']),
}

const normalizeTarget = (target: string): string | null => {
  const normalized = target.trim().toLowerCase()
  if (normalized === '_blank' || normalized === '_self') {
    return normalized
  }
  return null
}

const sanitizeHref = (href: string): string | null => {
  const trimmedHref = href.trim()
  if (!trimmedHref) {
    return null
  }

  if (trimmedHref.startsWith('/') || trimmedHref.startsWith('#')) {
    return trimmedHref
  }

  try {
    const parsed = new URL(trimmedHref, window.location.origin)
    if (ALLOWED_PROTOCOLS.has(parsed.protocol)) {
      return trimmedHref
    }
  } catch {
    return null
  }

  return null
}

const sanitizeNode = (node: ChildNode): void => {
  if (node.nodeType === Node.TEXT_NODE) {
    return
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    node.remove()
    return
  }

  const element = node as HTMLElement
  const tagName = element.tagName.toLowerCase()

  if (!ALLOWED_TAGS.has(tagName)) {
    if (STRIP_CONTENT_TAGS.has(tagName)) {
      element.remove()
      return
    }

    const parent = element.parentNode
    if (!parent) {
      element.remove()
      return
    }

    const childNodes = Array.from(element.childNodes)
    for (const childNode of childNodes) {
      parent.insertBefore(childNode, element)
      sanitizeNode(childNode as ChildNode)
    }
    element.remove()
    return
  }

  const allowedAttributes = ALLOWED_ATTRIBUTES[tagName] ?? new Set<string>()
  for (const attribute of Array.from(element.attributes)) {
    const attributeName = attribute.name.toLowerCase()
    if (attributeName.startsWith('on') || !allowedAttributes.has(attributeName)) {
      element.removeAttribute(attribute.name)
      continue
    }

    if (tagName === 'a' && attributeName === 'href') {
      const safeHref = sanitizeHref(attribute.value)
      if (safeHref) {
        element.setAttribute('href', safeHref)
      } else {
        element.removeAttribute(attribute.name)
      }
      continue
    }

    if (tagName === 'a' && attributeName === 'target') {
      const safeTarget = normalizeTarget(attribute.value)
      if (safeTarget) {
        element.setAttribute('target', safeTarget)
      } else {
        element.removeAttribute(attribute.name)
      }
    }
  }

  if (tagName === 'a') {
    if (element.getAttribute('target') === '_blank') {
      element.setAttribute('rel', 'noopener noreferrer')
    } else {
      element.removeAttribute('rel')
    }
  }

  for (const childNode of Array.from(element.childNodes)) {
    sanitizeNode(childNode as ChildNode)
  }
}

const sanitizeHtml = (html: string): string => {
  if (!html.trim() || typeof document === 'undefined') {
    return html
  }

  const template = document.createElement('template')
  template.innerHTML = html

  for (const childNode of Array.from(template.content.childNodes)) {
    sanitizeNode(childNode as ChildNode)
  }

  return template.innerHTML
}

interface SafeHtmlProps {
  html: string
  className?: string
}

export function SafeHtml({ html, className }: SafeHtmlProps) {
  const sanitizedHtml = useMemo(() => sanitizeHtml(html), [html])

  return (
    <div
      className={cn(
        'break-words leading-6 [&_a]:text-blue-600 [&_a]:underline-offset-2 [&_a]:transition-colors [&_a]:hover:underline [&_a]:hover:text-blue-700 dark:[&_a]:text-blue-400 dark:[&_a]:hover:text-blue-300',
        className,
      )}
      dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
    />
  )
}
