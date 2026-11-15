import { useCallback, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { cancelAppointment, completeAppointment, getAppointment } from '../api/appointments'
import { formatAppointmentDate } from '../appointments/validation'
import AppointmentStatusBadge from '../components/appointments/AppointmentStatusBadge'
import DemoBadge from '../components/auth/DemoBadge'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'
import { formatClockTime } from '../medications/display'
import { formatDateTime } from '../utils/format'
import { timeZoneLabel } from '../utils/timezones'

function Item({ label, children }) {
  return (
    <div className="border-b border-slate-100 py-3 last:border-b-0 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-base font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 whitespace-pre-line break-words text-lg text-slate-900 sm:col-span-2 sm:mt-0">
        {children || <span className="text-slate-600">Not provided</span>}
      </dd>
    </div>
  )
}

/**
 * /appointments/:appointmentId (owner: edit, cancel, mark completed) and
 * /linked/:profileId/appointments/:appointmentId (caretaker/family: read-only).
 */
export default function AppointmentDetail() {
  const { appointmentId, profileId } = useParams()
  const { state } = useLocation()
  const loader = useCallback((s) => getAppointment(appointmentId, { profileId }, s), [appointmentId, profileId])
  const { data: appt, error, reload } = useResource(loader)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // {variant, text}
  const backTo = profileId ? `/linked/${profileId}/appointments` : '/appointments'

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {error.response?.status === 404
            ? 'This appointment is not available. Your access may have been removed.'
            : getApiErrorMessage(error, 'We could not load this appointment.')}
        </Alert>
        <ButtonLink to={backTo} variant="secondary" className="mt-4">
          Back to appointments
        </ButtonLink>
      </div>
    )
  }
  if (!appt) return <PageLoader label="Loading appointment…" />

  async function act(action) {
    setBusy(true)
    setResult(null)
    try {
      await (action === 'cancel' ? cancelAppointment(appt.id) : completeAppointment(appt.id))
      setResult({ variant: 'success', text: action === 'cancel' ? 'The appointment was cancelled.' : 'Marked as completed.' })
      setConfirming(false)
    } catch (err) {
      setResult({ variant: 'error', text: getApiErrorMessage(err, 'That did not work. Please try again.') })
    }
    setBusy(false)
    reload()
  }

  const notice = result ?? (state?.notice ? { variant: 'success', text: state.notice } : null)

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            {appt.doctor_name}
            {appt.is_demo && <DemoBadge />}
          </span>
        }
        description={appt.specialization}
        actions={
          <>
            <ButtonLink to={backTo} variant="secondary">
              Back to appointments
            </ButtonLink>
            {appt.can_edit && <ButtonLink to={`/appointments/${appt.id}/edit`}>Edit</ButtonLink>}
          </>
        }
      />

      <div aria-live="polite" className="mb-6 empty:hidden">
        {notice && <Alert variant={notice.variant}>{notice.text}</Alert>}
      </div>

      <section aria-labelledby="when-heading" className="mb-6 rounded-2xl border border-teal-200 bg-teal-50/60 p-6 shadow-sm">
        <h2 id="when-heading" className="sr-only">Date and time</h2>
        <p className="text-2xl font-semibold text-slate-900">{formatAppointmentDate(appt.appointment_date)}</p>
        <p className="mt-1 text-4xl font-bold tabular-nums text-teal-800">{formatClockTime(appt.appointment_time)}</p>
        <p className="mt-2 text-base text-slate-600">{timeZoneLabel(appt.timezone)} time</p>
        <div className="mt-4">
          <AppointmentStatusBadge appointment={appt} />
        </div>
      </section>

      <section aria-labelledby="details-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="details-heading" className="text-2xl font-semibold text-slate-900">Details</h2>
        <dl className="mt-2">
          <Item label="Hospital or clinic">{appt.clinic_name}</Item>
          <Item label="Address">{appt.clinic_address}</Item>
          <Item label="Type">{appt.appointment_type}</Item>
          <Item label="Reason for visit">{appt.reason}</Item>
          <Item label="Notes">{appt.notes}</Item>
          {appt.status !== 'scheduled' && <Item label="Status updated">{formatDateTime(appt.status_changed_at)}</Item>}
        </dl>
      </section>

      {(appt.can_complete || appt.can_cancel) && (
        <section aria-labelledby="update-heading" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="update-heading" className="text-2xl font-semibold text-slate-900">Update this appointment</h2>
          {appt.can_complete && !confirming && (
            <p className="mt-2 text-lg text-slate-700">This appointment time has passed. Did it go ahead?</p>
          )}
          {confirming ? (
            <div role="group" aria-label="Confirm cancellation" className="mt-3 flex flex-col gap-3">
              <p className="text-lg text-slate-800">Cancel this appointment with {appt.doctor_name}? This cannot be undone.</p>
              <div className="flex flex-wrap gap-3">
                <Button variant="danger" disabled={busy} onClick={() => act('cancel')}>
                  {busy ? 'Cancelling…' : 'Yes, cancel it'}
                </Button>
                <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
                  No, keep it
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap gap-3">
              {appt.can_complete && (
                <Button disabled={busy} onClick={() => act('complete')}>
                  ✓ Mark as completed
                </Button>
              )}
              {appt.can_cancel && (
                <Button variant="secondary" disabled={busy} onClick={() => setConfirming(true)}>
                  ✕ Cancel appointment
                </Button>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
