import { Link } from 'react-router-dom'
import { FREQUENCY_LABELS } from '../../medications/validation'
import { formatClockTime } from '../../medications/display'
import { formatCalendarDate } from '../../utils/format'
import DemoBadge from '../auth/DemoBadge'

/** Medication cards. `linkTo(med)` returns the detail URL, or null for no link. */
export default function MedicationList({ medications, linkTo, emptyText }) {
  if (medications.length === 0) {
    return <p className="text-lg text-slate-600">{emptyText}</p>
  }
  return (
    <ul className="grid gap-4 md:grid-cols-2">
      {medications.map((med) => {
        const href = linkTo?.(med)
        const body = (
          <>
            <span className="flex flex-wrap items-center gap-2">
              <span className="break-words text-xl font-semibold text-slate-900">{med.name}</span>
              {med.status === 'discontinued' && (
                <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-base font-semibold text-slate-800">Stopped</span>
              )}
              {med.is_demo && <DemoBadge />}
            </span>
            <span className="mt-1 block text-lg text-slate-700">{med.dosage}</span>
            <span className="mt-2 block text-base text-slate-600">
              {FREQUENCY_LABELS[med.frequency]}: {med.times.map(formatClockTime).join(', ')}
            </span>
            <span className="mt-1 block text-base text-slate-500">
              From {formatCalendarDate(med.start_date)}
              {med.end_date ? ` until ${formatCalendarDate(med.end_date)}` : ''}
            </span>
          </>
        )
        return (
          <li key={med.id}>
            {href ? (
              <Link
                to={href}
                className="block h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-teal-600 hover:bg-teal-50"
              >
                {body}
              </Link>
            ) : (
              <div className="h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
