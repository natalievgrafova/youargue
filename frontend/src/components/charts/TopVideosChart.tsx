'use client'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { Video, VideoThread } from '@/lib/types'

interface Props { videos: Video[] }

const THREAD_COLORS = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#f43f5e']

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'k'
  return String(n)
}

function trunc(s: string, n = 36) { return s.length > n ? s.slice(0, n) + '…' : s }

interface ChartRow {
  name: string
  fullTitle: string
  channel: string
  threads: VideoThread[]
  totalComments: number
  slot_0: number; slot_1: number; slot_2: number; slot_3: number; slot_4: number; slot_rest: number
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d: ChartRow = payload[0]?.payload
  return (
    <div style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 10, padding: '12px 14px', maxWidth: 340 }}>
      <p style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 13, lineHeight: 1.4, marginBottom: 6 }}>{d.fullTitle}</p>
      <p style={{ color: '#475569', fontSize: 11, marginBottom: d.threads?.length ? 10 : 0 }}>
        {d.totalComments?.toLocaleString()} comments · {d.channel}
      </p>
      {d.threads?.length > 0 && (
        <>
          <p style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Top threads</p>
          {d.threads.slice(0, 3).map((t, i) => (
            <div key={i} style={{ marginBottom: 8, paddingLeft: 8, borderLeft: `2px solid ${THREAD_COLORS[i]}` }}>
              <p style={{ color: '#64748b', fontSize: 10, marginBottom: 2 }}>
                {t.author} · {t.likes} ♥ · {t.replies} replies
              </p>
              <p style={{ color: '#94a3b8', fontSize: 11, lineHeight: 1.4 }}>
                {t.text.length > 130 ? t.text.slice(0, 130) + '…' : t.text}
              </p>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

export default function TopVideosChart({ videos }: Props) {
  const data: ChartRow[] = videos.slice(0, 10).map(v => {
    const threads = v.threads ?? []
    const total = v.comment_count
    const slots = [0, 0, 0, 0, 0]

    if (threads.length === 0) {
      slots[0] = total
    } else {
      const totalSize = threads.slice(0, 5).reduce((s, t) => s + 1 + t.replies, 0) || 1
      let assigned = 0
      threads.slice(0, 5).forEach((t, i) => {
        const seg = Math.round((1 + t.replies) / totalSize * total)
        slots[i] = seg
        assigned += seg
      })
      // normalize: if rounding left a gap, add to last slot
      const diff = total - assigned
      if (diff !== 0) slots[Math.min(threads.length - 1, 4)] += diff
    }

    const slotSum = slots.reduce((a, b) => a + b, 0)
    return {
      name: trunc(v.title),
      fullTitle: v.title,
      channel: v.channel_name,
      threads,
      totalComments: total,
      slot_0: slots[0], slot_1: slots[1], slot_2: slots[2], slot_3: slots[3], slot_4: slots[4],
      slot_rest: Math.max(0, total - slotSum),
    }
  })

  return (
    <ResponsiveContainer width="100%" height={420}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 50, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={fmt}
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={260}
          tick={{ fill: '#cbd5e1', fontSize: 13 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        {(['slot_0','slot_1','slot_2','slot_3','slot_4'] as const).map((key, i) => (
          <Bar key={key} dataKey={key} stackId="a" fill={THREAD_COLORS[i]} fillOpacity={0.82} isAnimationActive={false} />
        ))}
        <Bar dataKey="slot_rest" stackId="a" fill="#1e293b" fillOpacity={0.9} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
