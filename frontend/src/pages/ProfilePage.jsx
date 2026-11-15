import { useLocation } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getMyProfile } from '../api/profile'
import ProfileDetails from '../components/profile/ProfileDetails'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

const SAVED_MESSAGES = {
  created: 'Your profile has been created.',
  updated: 'Your changes have been saved.',
}

/** Elderly user's own profile: details view, or a prompt to set it up. */
export default function ProfilePage() {
  const { state } = useLocation()
  const { loading, data: profile, error, reload } = useResource(getMyProfile)

  if (loading && !profile) return <PageLoader label="Loading your profile…" />

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">{getApiErrorMessage(error, 'We could not load your profile.')}</Alert>
        <Button variant="secondary" className="mt-4" onClick={reload}>
          Try again
        </Button>
      </div>
    )
  }

  if (!profile) {
    return (
      <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-3xl font-semibold text-slate-900">Set up your profile</h1>
        <p className="mt-3 text-lg text-slate-600">
          Your profile tells the people who care for you how to reach you and who to contact in an emergency. It only
          takes a few minutes.
        </p>
        <ButtonLink to="/profile/setup" className="mt-6">
          Set up my profile
        </ButtonLink>
      </section>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="My profile"
        description="Only you, and the family members and caretakers you invite, can see this information."
        actions={
          <>
            <ButtonLink to="/profile/edit">Edit profile</ButtonLink>
            <ButtonLink to="/connections" variant="secondary">
              Manage connections
            </ButtonLink>
          </>
        }
      />
      {SAVED_MESSAGES[state?.saved] && (
        <div className="mb-6">
          <Alert variant="success">{SAVED_MESSAGES[state.saved]}</Alert>
        </div>
      )}
      <ProfileDetails profile={profile} />
    </div>
  )
}
