import { getApiErrorMessage } from '../api/client'
import { listConnections, listInvitations } from '../api/linking'
import { getMyProfile } from '../api/profile'
import ConnectionList from '../components/linking/ConnectionList'
import InvitationCreator from '../components/linking/InvitationCreator'
import InvitationList from '../components/linking/InvitationList'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

async function loadConnectionsPage(signal) {
  const profile = await getMyProfile(signal)
  if (!profile) return { profile: null, invitations: [], connections: [] }
  const [invitations, connections] = await Promise.all([listInvitations(signal), listConnections(signal)])
  return { profile, invitations, connections }
}

/** Elderly user: invite people and manage who can see the profile. */
export default function Connections() {
  const { loading, data, error, reload } = useResource(loadConnectionsPage)

  if (loading && !data) return <PageLoader label="Loading your connections…" />
  if (error && !data) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">{getApiErrorMessage(error, 'We could not load your connections.')}</Alert>
        <Button variant="secondary" className="mt-4" onClick={reload}>
          Try again
        </Button>
      </div>
    )
  }

  if (!data.profile) {
    return (
      <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-3xl font-semibold text-slate-900">Create your profile first</h1>
        <p className="mt-3 text-lg text-slate-600">
          Before inviting family members or caretakers, please set up your profile so they know how to help you.
        </p>
        <ButtonLink to="/profile/setup" className="mt-6">
          Set up my profile
        </ButtonLink>
      </section>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader
        title="Family & caretakers"
        description="Invite the people who support you, and choose who can see your profile."
      />
      <InvitationCreator onCreated={reload} />
      <ConnectionList connections={data.connections} onChanged={reload} />
      <InvitationList invitations={data.invitations} onChanged={reload} />
    </div>
  )
}
