import { useLocation } from 'react-router-dom'
import AppointmentsOverview from '../components/appointments/AppointmentsOverview'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { useAuth } from '../hooks/useAuth'

const linkTo = (a) => `/appointments/${a.id}`

/** /appointments: the elderly user's own appointments. */
export default function AppointmentsDashboard() {
  const { user } = useAuth()
  const { state } = useLocation()
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="My appointments"
        description="Keep track of doctor and hospital visits. Your family and caretakers can see them too."
        actions={<ButtonLink to="/appointments/new">Add appointment</ButtonLink>}
      />
      {state?.notice && (
        <div className="mb-6">
          <Alert variant="success">{state.notice}</Alert>
        </div>
      )}
      {user.is_demo && (
        <div role="note" className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-base text-amber-900">
          <strong>Demo account:</strong> these appointments are sample data shared by everyone using the demo.
        </div>
      )}
      <AppointmentsOverview canModify linkTo={linkTo} />
    </div>
  )
}
