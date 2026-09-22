import { MessageSquare } from 'lucide-react'
import type { Topic } from '@/lib/types'

interface Props {
  topic: Topic
  selected: boolean
  onClick: () => void
}

export default function TopicCard({ topic, selected, onClick }: Props) {
  const { topic: name, pro_pct, con_pct, total } = topic
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-4 transition-all ${
        selected
          ? 'border-violet-500 bg-violet-500/10 shadow-lg shadow-violet-500/10'
          : 'border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-800/50'
      }`}
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className="font-semibold text-white capitalize text-sm leading-tight">{name}</span>
        <span className="flex items-center gap-1 text-xs text-slate-500 shrink-0 ml-2">
          <MessageSquare className="h-3 w-3" /> {total}
        </span>
      </div>

      {/* Stance bar */}
      <div className="flex rounded-full overflow-hidden h-2 gap-px">
        <div
          className="transition-all"
          style={{ width: `${pro_pct}%`, backgroundColor: '#10b981' }}
        />
        <div
          className="transition-all"
          style={{ width: `${con_pct}%`, backgroundColor: '#f43f5e' }}
        />
      </div>

      <div className="flex justify-between mt-1.5">
        <span className="text-[10px] font-medium text-emerald-500">PRO {pro_pct}%</span>
        <span className="text-[10px] font-medium text-rose-500">CON {con_pct}%</span>
      </div>
    </button>
  )
}
