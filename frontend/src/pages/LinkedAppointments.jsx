import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getLinkedProfile } from '../api/linking'
import AppointmentsOverview from '../components/appointments/AppointmentsOverview'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

/** /linked/:profileId/appointments: read-only appointments for caretakers/family members. */
export default function LinkedAppointments() {
  const { profileId } = useParams()
  const loader = useCallback((signal) => getLinkedProfile(profileId, signal), [profileId])
  const { loading, data, error } = useResource(loader)
  const linkTo = useCallback((a) => `/linked/${profileId}/appointments/${a.id}`, [profileId])

  if (loading) return <PageLoader label="Loading…" />
  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {error.response?.status === 404
            ? 'This profile is not available. You may not be connected, or your access may have been removed.'
            : getApiErrorMessage(error, 'We could not load this profile.')}
        </Alert>
        <ButtonLink to="/linked" variant="secondary" className="mt-4">
          Back to people you support
        </ButtonLink>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title={`${data.profile.full_name}'s appointments`}
        description="You can view appointments. Only they can add, change or cancel them."
        actions={
          <ButtonLink to={`/linked/${profileId}`} variant="secondary">
            Back to profile
          </ButtonLink>
        }
      />
      <AppointmentsOverview profileId={profileId} canModify={false} linkTo={linkTo} />
    </div>
  )
}
