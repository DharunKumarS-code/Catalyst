import { formatAppointmentDate } from '../../appointments/validation'
import { formatClockTime } from '../../medications/display'
import { formatDateTime } from '../../utils/format'

const KINDS = {
  dose_taken: { icon: '✓', tone: 'text-emerald-800 bg-emerald-50', text: (i) => `Took ${i.subject} (${formatClockTime(i.local_time)} dose)` },
  dose_missed: { icon: '✕', tone: 'text-rose-800 bg-rose-50', text: (i) => `Missed ${i.subject} (${formatClockTime(i.local_time)} dose)` },
  appointment_completed: {
    icon: '✓',
    tone: 'text-emerald-800 bg-emerald-50',
    text: (i) => `Appointment with ${i.subject}${i.place ? ` at ${i.place}` : ''} marked completed`,
  },
  appointment_cancelled: {
    icon: '✕',
    tone: 'text-slate-700 bg-slate-100',
    text: (i) => `Appointment with ${i.subject} on ${formatAppointmentDate(i.local_date)} was cancelled`,
  },
}

/** Events the elderly person actually recorded in the last 7 days. Nothing is inferred. */
export default function RecentActivity({ items }) {
  if (items.length === 0) {
    return <p className="text-lg text-slate-600">Nothing has been recorded in the last 7 days.</p>
  }
  return (
    <ol className="flex flex-col gap-3">
      {items.map((item, i) => {
        const kind = KINDS[item.kind]
        return (
          <li key={`${item.kind}-${item.at}-${i}`} className="flex items-start gap-3" data-testid="activity-item">
            <span aria-hidden="true" className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-bold ${kind.tone}`}>
              {kind.icon}
            </span>
            <span>
              <span className="block text-lg text-slate-900">{kind.text(item)}</span>
              <span className="block text-base text-slate-500">Recorded {formatDateTime(item.at)}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
