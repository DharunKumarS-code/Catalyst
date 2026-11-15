const VARIANTS = {
  ok: { dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  warn: { dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-800 ring-amber-200' },
  error: { dot: 'bg-rose-500', chip: 'bg-rose-50 text-rose-800 ring-rose-200' },
  pending: { dot: 'bg-slate-400 animate-pulse', chip: 'bg-slate-100 text-slate-700 ring-slate-200' },
}

export default function StatusBadge({ variant = 'pending', children }) {
  const v = VARIANTS[variant] ?? VARIANTS.pending
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${v.chip}`}>
      <span className={`h-2.5 w-2.5 rounded-full ${v.dot}`} aria-hidden="true" />
      {children}
    </span>
  )
}
