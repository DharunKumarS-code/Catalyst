import { useCallback } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { listAppointments } from '../../api/appointments'
import { useResource } from '../../hooks/useResource'
import Alert from '../ui/Alert'
import { ButtonLink } from '../ui/Button'
import PageLoader from '../ui/PageLoader'
import AppointmentList from './AppointmentList'

/** Upcoming appointments and history, for the owner or (read-only) a linked member. */
export default function AppointmentsOverview({ profileId, canModify, linkTo }) {
  const loadUpcoming = useCallback((s) => listAppointments({ profileId, view: 'upcoming' }, s), [profileId])
  const loadHistory = useCallback((s) => listAppointments({ profileId, view: 'history' }, s), [profileId])
  const upcoming = useResource(loadUpcoming)
  const history = useResource(loadHistory)

  const error = upcoming.error || history.error
  if (error) {
    if (canModify && error.response?.status === 409) {
      return (
        <div className="flex flex-col items-start gap-4">
          <Alert variant="info">Create your profile first, so we know your time zone for appointment times.</Alert>
          <ButtonLink to="/profile/setup">Set up my profile</ButtonLink>
        </div>
      )
    }
    return <Alert variant="error">{getApiErrorMessage(error, 'We could not load appointments.')}</Alert>
  }
  if (!upcoming.data || !history.data) return <PageLoader label="Loading appointments…" />

  const needsUpdate = history.data.filter((a) => a.status === 'scheduled')

  return (
    <div className="flex flex-col gap-10">
      {canModify && needsUpdate.length > 0 && (
        <div role="note" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-lg text-amber-900">
          {needsUpdate.length === 1 ? 'One past appointment needs' : `${needsUpdate.length} past appointments need`} an
          update. Open it to mark it completed or cancelled.
        </div>
      )}
      <section aria-labelledby="upcoming-heading">
        <h2 id="upcoming-heading" className="mb-4 text-2xl font-semibold text-slate-900">
          Upcoming appointments
        </h2>
        <AppointmentList appointments={upcoming.data} linkTo={linkTo} emptyText="No upcoming appointments." />
      </section>
      <section aria-labelledby="history-heading">
        <h2 id="history-heading" className="mb-4 text-2xl font-semibold text-slate-900">
          Past and cancelled appointments
        </h2>
        <AppointmentList appointments={history.data} linkTo={linkTo} emptyText="No past appointments yet." />
      </section>
    </div>
  )
}
