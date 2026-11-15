import { useLocation } from 'react-router-dom'
import MedicationOverview from '../components/medications/MedicationOverview'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { useAuth } from '../hooks/useAuth'

const medicationHref = (med) => `/medications/${med.id}`

/** /medications: the elderly user's own medicines, today's doses and adherence. */
export default function MedicationsDashboard() {
  const { user } = useAuth()
  const { state } = useLocation()

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="My medicines"
        description="Record each dose as taken or missed. Nothing is ever marked as taken for you."
        actions={<ButtonLink to="/medications/new">Add medication</ButtonLink>}
      />
      {state?.notice && (
        <div className="mb-6">
          <Alert variant="success">{state.notice}</Alert>
        </div>
      )}
      {user.is_demo && (
        <div role="note" className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-base text-amber-900">
          <strong>Demo account:</strong> these medicines are sample data shared by everyone using the demo. They are not
          medical advice.
        </div>
      )}
      <MedicationOverview canModify medicationHref={medicationHref} historyHref="/medications/history" />
    </div>
  )
}
