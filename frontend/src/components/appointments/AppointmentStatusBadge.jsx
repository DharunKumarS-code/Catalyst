// Status is conveyed by text and an icon shape, never by colour alone.
const STYLES = {
  scheduled: { label: 'Scheduled', icon: '○', chip: 'bg-teal-50 text-teal-900 ring-teal-300' },
  awaiting: { label: 'Needs update', icon: '!', chip: 'bg-amber-50 text-amber-900 ring-amber-300' },
  completed: { label: 'Completed', icon: '✓', chip: 'bg-emerald-50 text-emerald-900 ring-emerald-300' },
  cancelled: { label: 'Cancelled', icon: '✕', chip: 'bg-slate-100 text-slate-700 ring-slate-300' },
}

export default function AppointmentStatusBadge({ appointment }) {
  const key = appointment.status === 'scheduled' && appointment.is_past ? 'awaiting' : appointment.status
  const style = STYLES[key] ?? STYLES.scheduled
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-base font-semibold ring-1 ring-inset ${style.chip}`}
      data-testid="appointment-status"
    >
      <span aria-hidden="true" className="font-bold">
        {style.icon}
      </span>
      {style.label}
    </span>
  )
}
