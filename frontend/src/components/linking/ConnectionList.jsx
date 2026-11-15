import { useState } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { revokeConnection } from '../../api/linking'
import RoleBadge from '../auth/RoleBadge'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import { formatDate } from '../../utils/format'

/** Elderly user's connected caretakers/family with a two-step "remove access". */
export default function ConnectionList({ connections, onChanged }) {
  const [confirmId, setConfirmId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  async function handleRevoke(connection) {
    setBusy(true)
    setMessage(null)
    try {
      await revokeConnection(connection.id)
      setMessage({ variant: 'success', text: `${connection.member.name} can no longer see your profile.` })
      setConfirmId(null)
      onChanged()
    } catch (err) {
      setMessage({ variant: 'error', text: getApiErrorMessage(err, 'We could not remove this connection.') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="connections-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 id="connections-heading" className="text-2xl font-semibold text-slate-900">People connected to you</h2>
      <p className="mt-2 text-lg text-slate-600">These people can see your profile. You can remove access at any time.</p>
      <div aria-live="polite" className="mt-3 empty:mt-0">
        {message && <Alert variant={message.variant}>{message.text}</Alert>}
      </div>
      {connections.length === 0 ? (
        <p className="mt-4 text-lg text-slate-600">No one is connected yet. Create an invitation above to get started.</p>
      ) : (
        <ul className="mt-4 flex flex-col gap-3">
          {connections.map((c) => (
            <li key={c.id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-lg font-semibold text-slate-900">{c.member.name}</p>
                  <p className="break-all text-base text-slate-600">{c.member.email}</p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-base text-slate-600">
                    <RoleBadge role={c.role} /> Connected since {formatDate(c.connected_at)}
                  </p>
                </div>
                {confirmId !== c.id && (
                  <Button variant="secondary" onClick={() => setConfirmId(c.id)} aria-label={`Remove access for ${c.member.name}`}>
                    Remove access
                  </Button>
                )}
              </div>
              {confirmId === c.id && (
                <div role="group" aria-label={`Confirm removing ${c.member.name}`} className="mt-4 rounded-xl bg-rose-50 p-4">
                  <p className="text-lg text-rose-900">
                    Remove <strong>{c.member.name}</strong>? They will immediately lose access to your profile.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <Button variant="danger" onClick={() => handleRevoke(c)} disabled={busy}>
                      {busy ? 'Removing…' : 'Yes, remove access'}
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirmId(null)} disabled={busy}>
                      Keep connected
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
