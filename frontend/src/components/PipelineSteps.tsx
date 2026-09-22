const steps = [
  { n: '①', label: 'Fetch Videos' },
  { n: '②', label: 'Extract Threads' },
  { n: '③', label: 'Detect Topics' },
  { n: '④', label: 'Filter Relevance' },
  { n: '⑤', label: 'Classify Stance' },
]

interface Props { activeStep: number }

export default function PipelineSteps({ activeStep }: Props) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-1">
      {steps.map((s, i) => {
        const done = i < activeStep
        const active = i === activeStep
        return (
          <div key={i} className="flex items-center">
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
                active
                  ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                  : done
                  ? 'text-emerald-500'
                  : 'text-slate-600'
              }`}
            >
              <span>{done ? '✓' : s.n}</span>
              <span>{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-6 h-px mx-1 ${done ? 'bg-emerald-500/50' : 'bg-slate-800'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
