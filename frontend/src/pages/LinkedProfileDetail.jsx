import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getLinkedProfile } from '../api/linking'
import RoleBadge from '../components/auth/RoleBadge'
import ProfileDetails from '../components/profile/ProfileDetails'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'
import { formatDate } from '../utils/format'

export default function LinkedProfileDetail() {
  const { profileId } = useParams()
  const loader = useCallback((signal) => getLinkedProfile(profileId, signal), [profileId])
  const { loading, data, error } = useResource(loader)

  if (loading) return <PageLoader label="Loading profile…" />

  if (error) {
    const notFound = error.response?.status === 404
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {notFound
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
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={data.profile.full_name}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            You are connected as <RoleBadge role={data.role} /> since {formatDate(data.connected_at)}.
          </span>
        }
        actions={
          <>
            <ButtonLink to="/linked" variant="secondary">
              Back to list
            </ButtonLink>
            <ButtonLink to={`/linked/${profileId}/medications`}>View medicines</ButtonLink>
            <ButtonLink to={`/linked/${profileId}/appointments`}>View appointments</ButtonLink>
          </>
        }
      />
      <ProfileDetails profile={data.profile} />
    </div>
  )
}
