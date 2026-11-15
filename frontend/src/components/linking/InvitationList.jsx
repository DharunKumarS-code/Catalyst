import { useState } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { cancelInvitation } from '../../api/linking'
import { ROLE_LABELS } from '../../auth/roles'
import { formatDateTime } from '../../utils/format'
import Alert from '../ui/Alert'
import Button from '../ui/Button'

const STATUS = {
  pending: { label: 'Waiting to be used', className: 'bg-sky-50 text-sky-800 ring-sky-200' },
  redeemed: { label: 'Used', className: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  expired: { label: 'Expired', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  revoked: { label: 'Cancelled', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  locked: { label: 'Blocked after misuse', className: 'bg-rose-50 text-rose-800 ring-rose-200' },
}

export default function InvitationList({ invitations, onChanged }) {
  const [busyId, setBusyId] = useState(null)
  const [message, setMessage] = useState(null)

  async function handleCancel(id) {
    setBusyId(id)
    setMessage(null)
    try {
      await cancelInvitation(id)
      setMessage({ variant: 'success', text: 'The invitation has been cancelled. Its code no longer works.' })
      onChanged()
    } catch (err) {
      setMessage({ variant: 'error', text: getApiErrorMessage(err, 'We could not cancel the invitation.') })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section aria-labelledby="invitations-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 id="invitations-heading" className="text-2xl font-semibold text-slate-900">Your invitations</h2>
      <div aria-live="polite" className="mt-3 empty:mt-0">
        {message && <Alert variant={message.variant}>{message.text}</Alert>}
      </div>
      {invitations.length === 0 ? (
        <p className="mt-3 text-lg text-slate-600">You have not created any invitations yet.</p>
      ) : (
        <ul className="mt-4 flex flex-col gap-3">
          {invitations.map((inv) => {
            const status = STATUS[inv.status] ?? STATUS.expired
            return (
              <li key={inv.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4">
                <div>
                  <p className="text-lg font-medium text-slate-900">{ROLE_LABELS[inv.role]} invitation</p>
                  <p className="text-base text-slate-600">
                    Created {formatDateTime(inv.created_at)}
                    {inv.status === 'pending' && <> · expires {formatDateTime(inv.expires_at)}</>}
                  </p>
                  <span className={`mt-2 inline-flex rounded-full px-3 py-0.5 text-base font-medium ring-1 ring-inset ${status.className}`}>
                    {status.label}
                  </span>
                </div>
                {inv.status === 'pending' && (
                  <Button
                    variant="secondary"
                    onClick={() => handleCancel(inv.id)}
                    disabled={busyId === inv.id}
                    aria-label={`Cancel ${ROLE_LABELS[inv.role].toLowerCase()} invitation created ${formatDateTime(inv.created_at)}`}
                  >
                    {busyId === inv.id ? 'Cancelling…' : 'Cancel invitation'}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
