import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getLinkedProfile } from '../api/linking'
import MedicationOverview from '../components/medications/MedicationOverview'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

/** /linked/:profileId/medications: medication view for caretakers/family members (read-only, except
 *  doses a caretaker has been allowed to record). */
export default function LinkedMedications() {
  const { profileId } = useParams()
  const loader = useCallback((signal) => getLinkedProfile(profileId, signal), [profileId])
  const { loading, data, error } = useResource(loader)
  const medicationHref = useCallback((med) => `/linked/${profileId}/medications/${med.id}`, [profileId])

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
        title={`${data.profile.full_name}'s medicines`}
        description={
          data.can_record_doses
            ? 'You can record doses you give. Only they can change their medicines.'
            : 'You can view medicines and doses. Only they can change medicines.'
        }
        actions={
          <ButtonLink to={`/linked/${profileId}`} variant="secondary">
            Back to profile
          </ButtonLink>
        }
      />
      <MedicationOverview
        profileId={profileId}
        canModify={false}
        medicationHref={medicationHref}
        historyHref={`/linked/${profileId}/medications/history`}
      />
    </div>
  )
}
