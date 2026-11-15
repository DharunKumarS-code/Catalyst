import { useState } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { setDoseStatus } from '../../api/medications'
import { formatClockTime } from '../../medications/display'
import { formatCalendarDate } from '../../utils/format'
import { timeZoneLabel } from '../../utils/timezones'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import DoseStatusBadge from './DoseStatusBadge'

/**
 * Today's doses. With `canModify`, each due dose gets "Taken" / "Missed" controls.
 * The status the user saw is sent as `expected_status`, so a double tap or a stale
 * screen can never record a dose twice.
 */
export default function TodaySchedule({ schedule, canModify = false, onChanged, emptyText }) {
  const [busyId, setBusyId] = useState(null)
  const [message, setMessage] = useState(null)

  async function record(dose, status) {
    if (busyId) return
    setBusyId(dose.id)
    setMessage(null)
    try {
      const updated = await setDoseStatus(dose.id, status, dose.status)
      setMessage({
        variant: 'success',
        text: `${updated.medication_name} at ${formatClockTime(updated.local_time)} recorded as ${updated.status}.`,
      })
    } catch (err) {
      setMessage({ variant: 'error', text: getApiErrorMessage(err, 'We could not record this dose.') })
    } finally {
      setBusyId(null)
      onChanged?.()
    }
  }

  return (
    <section aria-labelledby="today-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="today-heading" className="text-2xl font-semibold text-slate-900">
          Today&rsquo;s medicines
        </h2>
        <p className="text-base text-slate-600">
          {formatCalendarDate(schedule.date)} &middot; {timeZoneLabel(schedule.timezone)} time
        </p>
      </div>

      <div aria-live="polite" className="mt-4 empty:hidden">
        {message && <Alert variant={message.variant}>{message.text}</Alert>}
      </div>

      {schedule.doses.length === 0 ? (
        <p className="mt-4 text-lg text-slate-600">{emptyText ?? 'No medicines are scheduled for today.'}</p>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100">
          {schedule.doses.map((dose) => (
            <li key={dose.id} className="flex flex-wrap items-center gap-4 py-4" data-testid="dose-row">
              <span className="w-28 shrink-0 text-2xl font-semibold tabular-nums text-slate-900">
                {formatClockTime(dose.local_time)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="break-words text-xl font-semibold text-slate-900">{dose.medication_name}</p>
                <p className="text-lg text-slate-600">{dose.dosage}</p>
              </div>
              <DoseStatusBadge dose={dose} />
              {canModify && (dose.can_mark_taken || dose.can_mark_missed) && (
                <div className="flex w-full flex-wrap gap-2 sm:w-auto">
                  {dose.can_mark_taken && (
                    <Button
                      onClick={() => record(dose, 'taken')}
                      disabled={busyId !== null}
                      aria-label={`Mark ${dose.medication_name} at ${formatClockTime(dose.local_time)} as taken`}
                    >
                      {busyId === dose.id ? 'Saving…' : '✓ Taken'}
                    </Button>
                  )}
                  {dose.can_mark_missed && (
                    <Button
                      variant="secondary"
                      onClick={() => record(dose, 'missed')}
                      disabled={busyId !== null}
                      aria-label={`Mark ${dose.medication_name} at ${formatClockTime(dose.local_time)} as missed`}
                    >
                      ✕ Missed
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
