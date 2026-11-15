import { doseDisplayStatus } from '../../medications/display'

// Status is conveyed by text and an icon shape, never by colour alone.
const STYLES = {
  taken: { label: 'Taken', icon: '✓', chip: 'bg-emerald-50 text-emerald-900 ring-emerald-300' },
  missed: { label: 'Missed', icon: '✕', chip: 'bg-rose-50 text-rose-900 ring-rose-300' },
  overdue: { label: 'Not recorded', icon: '!', chip: 'bg-amber-50 text-amber-900 ring-amber-300' },
  upcoming: { label: 'Upcoming', icon: '○', chip: 'bg-slate-100 text-slate-800 ring-slate-300' },
  cancelled: { label: 'Cancelled', icon: '–', chip: 'bg-slate-100 text-slate-600 ring-slate-300' },
}

export default function DoseStatusBadge({ dose }) {
  const style = STYLES[doseDisplayStatus(dose)] ?? STYLES.upcoming
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-base font-semibold ring-1 ring-inset ${style.chip}`}
      data-testid="dose-status"
    >
      <span aria-hidden="true" className="font-bold">
        {style.icon}
      </span>
      {style.label}
    </span>
  )
}
