// Delivery status as text + icon (never colour alone).
const STYLES = {
  sent: { label: 'Sent', icon: '✓', chip: 'bg-emerald-50 text-emerald-900 ring-emerald-300' },
  preview: { label: 'Preview only', icon: '◇', chip: 'bg-sky-50 text-sky-900 ring-sky-300' },
  pending: { label: 'Waiting to send', icon: '…', chip: 'bg-slate-100 text-slate-800 ring-slate-300' },
  sending: { label: 'Sending', icon: '…', chip: 'bg-slate-100 text-slate-800 ring-slate-300' },
  failed: { label: 'Failed', icon: '✕', chip: 'bg-rose-50 text-rose-900 ring-rose-300' },
  skipped: { label: 'Not sent', icon: '–', chip: 'bg-amber-50 text-amber-900 ring-amber-300' },
}

export default function NotificationStatusBadge({ status }) {
  const s = STYLES[status] ?? STYLES.pending
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-base font-semibold ring-1 ring-inset ${s.chip}`} data-testid="notification-status">
      <span aria-hidden="true" className="font-bold">{s.icon}</span>
      {s.label}
    </span>
  )
}
