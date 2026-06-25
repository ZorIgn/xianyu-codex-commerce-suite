interface SystemDisclaimerContentProps {
  content: string
}

export function SystemDisclaimerContent({ content }: SystemDisclaimerContentProps) {
  const sections = content
    .split(/\n{2,}/)
    .map((section) => section.trim())
    .filter(Boolean)

  return (
    <div className="space-y-4 text-sm leading-7 text-slate-700 dark:text-slate-300">
      {sections.map((section, index) => (
        <p key={`${index}-${section.slice(0, 20)}`} className="whitespace-pre-wrap break-words">
          {section}
        </p>
      ))}
    </div>
  )
}
