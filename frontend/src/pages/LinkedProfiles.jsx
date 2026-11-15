import { getApiErrorMessage } from '../api/client'
import { listLinkedProfiles } from '../api/linking'
import RoleBadge from '../components/auth/RoleBadge'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'
import { formatDate } from '../utils/format'

/** Caretaker / family member: the elderly profiles they are authorized to see. */
export default function LinkedProfiles() {
  const { loading, data, error, reload } = useResource(listLinkedProfiles)

  if (loading && !data) return <PageLoader label="Loading the people you support…" />

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="People you support"
        description="Profiles shared with you by the people you care for."
        actions={<ButtonLink to="/join">Enter an invitation code</ButtonLink>}
      />
      {error && (
        <div className="mb-6">
          <Alert variant="error">{getApiErrorMessage(error, 'We could not load this list.')}</Alert>
          <Button variant="secondary" className="mt-3" onClick={reload}>
            Try again
          </Button>
        </div>
      )}
      {data && data.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <p className="text-lg text-slate-700">You are not connected to anyone yet.</p>
          <p className="mt-2 text-base text-slate-600">
            Ask the person you care for to create an invitation code in their ElderCare Connect account.
          </p>
        </div>
      )}
      {data && data.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {data.map((p) => (
            <li key={p.relationship_id} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-900">{p.full_name}</h2>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-base text-slate-600">
                You are their <RoleBadge role={p.role} />
              </p>
              <p className="mt-1 text-base text-slate-600">Connected since {formatDate(p.connected_at)}</p>
              <ButtonLink to={`/linked/${p.profile_id}`} className="mt-4 self-start" aria-label={`View ${p.full_name}’s profile`}>
                View profile
              </ButtonLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
