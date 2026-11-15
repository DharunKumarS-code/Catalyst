import { useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { createAppointment, getAppointment, updateAppointment } from '../api/appointments'
import AppointmentForm from '../components/appointments/AppointmentForm'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'
import { formatAppointmentWhen } from '../appointments/validation'

const noAppointment = async () => null

/** /appointments/new and /appointments/:appointmentId/edit */
export default function AppointmentEditor() {
  const { appointmentId } = useParams()
  const navigate = useNavigate()
  const editing = Boolean(appointmentId)
  const loader = useCallback(
    (signal) => (appointmentId ? getAppointment(appointmentId, {}, signal) : noAppointment()),
    [appointmentId],
  )
  const { loading, data: appointment, error } = useResource(loader)

  if (loading) return <PageLoader label="Loading appointment…" />
  if (error || (editing && !appointment?.can_edit)) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {error
            ? getApiErrorMessage(error, 'We could not load this appointment.')
            : 'Only upcoming, scheduled appointments can be edited.'}
        </Alert>
        <ButtonLink to="/appointments" variant="secondary" className="mt-4">
          Back to appointments
        </ButtonLink>
      </div>
    )
  }

  async function handleSubmit(payload) {
    const saved = editing ? await updateAppointment(appointmentId, payload) : await createAppointment(payload)
    navigate(`/appointments/${saved.id}`, {
      state: { notice: `${editing ? 'Appointment updated' : 'Appointment added'}: ${formatAppointmentWhen(saved)}.` },
    })
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={editing ? 'Edit appointment' : 'Add an appointment'}
        description="Fields marked optional can be left empty."
      />
      <AppointmentForm
        initialAppointment={appointment}
        submitLabel={editing ? 'Save changes' : 'Add appointment'}
        onSubmit={handleSubmit}
        onCancel={() => navigate(editing ? `/appointments/${appointmentId}` : '/appointments')}
      />
    </div>
  )
}
