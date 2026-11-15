import { formatClockTime } from '../../medications/display'
import { formatCalendarDate, formatDateTime } from '../../utils/format'
import DoseStatusBadge from './DoseStatusBadge'

/** Past doses grouped by the elderly user's local date, newest first. */
export default function DoseHistory({ doses, showMedication = true }) {
  if (doses.length === 0) {
    return <p className="text-lg text-slate-600">No doses were due in this period.</p>
  }
  const groups = []
  for (const dose of doses) {
    const last = groups[groups.length - 1]
    if (last?.date === dose.local_date) last.doses.push(dose)
    else groups.push({ date: dose.local_date, doses: [dose] })
  }
  return (
    <div className="flex flex-col gap-6">
      {groups.map((group) => (
        <section key={group.date} aria-label={formatCalendarDate(group.date)}>
          <h3 className="text-xl font-semibold text-slate-900">{formatCalendarDate(group.date)}</h3>
          <ul className="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {group.doses.map((dose) => (
              <li key={dose.id} className="flex flex-wrap items-center gap-4 px-4 py-3">
                <span className="w-24 shrink-0 text-lg font-semibold tabular-nums text-slate-900">
                  {formatClockTime(dose.local_time)}
                </span>
                <div className="min-w-0 flex-1">
                  {showMedication && (
                    <p className="break-words text-lg font-medium text-slate-900">
                      {dose.medication_name} <span className="font-normal text-slate-600">&middot; {dose.dosage}</span>
                    </p>
                  )}
                  {dose.status_changed_at && dose.status !== 'pending' && (
                    <p className="text-base text-slate-500">Recorded {formatDateTime(dose.status_changed_at)}</p>
                  )}
                </div>
                <DoseStatusBadge dose={dose} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
