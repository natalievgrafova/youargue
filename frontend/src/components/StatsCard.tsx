import type { LucideIcon } from 'lucide-react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon: LucideIcon
  color?: string
}

export default function StatsCard({ label, value, sub, icon: Icon, color = '#8b5cf6' }: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 flex items-start gap-4">
      <div
        className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: color + '1a' }}
      >
        <Icon className="h-5 w-5" style={{ color }} />
      </div>
      <div>
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
        <p className="mt-1 text-2xl font-bold text-white">{value}</p>
        {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
      </div>
    </div>
  )
}
