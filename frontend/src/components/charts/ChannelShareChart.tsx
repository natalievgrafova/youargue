'use client'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { ChannelStats } from '@/lib/types'

interface Props { stats: Record<string, ChannelStats> }

export default function ChannelShareChart({ stats }: Props) {
  const data = Object.values(stats)
    .filter(s => s.total_comments > 0)
    .map(s => ({ name: s.name, value: s.total_comments, color: s.color }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="45%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((d, i) => (
            <Cell key={i} fill={d.color} fillOpacity={0.9} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
          formatter={(val: number) => val.toLocaleString() + ' comments'}
        />
        <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
