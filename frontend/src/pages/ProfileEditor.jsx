import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { createMyProfile, getMyProfile, updateMyProfile } from '../api/profile'
import ProfileForm from '../components/profile/ProfileForm'
import Alert from '../components/ui/Alert'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useAuth } from '../hooks/useAuth'
import { useResource } from '../hooks/useResource'

/** /profile/setup and /profile/edit: creates the profile if missing, otherwise edits it. */
export default function ProfileEditor() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { loading, data: profile, error } = useResource(getMyProfile)

  if (loading) return <PageLoader label="Loading your profile…" />
  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">{getApiErrorMessage(error, 'We could not load your profile.')}</Alert>
      </div>
    )
  }

  const creating = !profile

  async function handleSubmit(payload) {
    if (creating) await createMyProfile(payload)
    else await updateMyProfile(payload)
    navigate('/profile', { state: { saved: creating ? 'created' : 'updated' } })
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={creating ? 'Set up your profile' : 'Edit your profile'}
        description="Fields marked optional can be left empty. You can change these details at any time."
      />
      {user.is_demo && (
        <div role="note" className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-base text-amber-900">
          <strong>Demo account:</strong> this profile is shared with everyone using the demo. Please enter made-up
          details only.
        </div>
      )}
      <ProfileForm
        initialProfile={profile}
        submitLabel={creating ? 'Create my profile' : 'Save changes'}
        onSubmit={handleSubmit}
        onCancel={creating ? undefined : () => navigate('/profile')}
      />
    </div>
  )
}
