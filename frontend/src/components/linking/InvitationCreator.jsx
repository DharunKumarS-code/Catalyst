import { useEffect, useRef, useState } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { createInvitation } from '../../api/linking'
import { ROLE_LABELS, ROLES } from '../../auth/roles'
import { formatDateTime } from '../../utils/format'
import Alert from '../ui/Alert'
import Button from '../ui/Button'

const CHOICES = [
  { value: ROLES.FAMILY_MEMBER, title: 'A family member', text: 'A relative who wants to stay informed.' },
  { value: ROLES.CARETAKER, title: 'A caretaker', text: 'Someone who helps look after you.' },
]

export default function InvitationCreator({ onCreated }) {
  const [role, setRole] = useState(ROLES.FAMILY_MEMBER)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null)
  const [copied, setCopied] = useState(false)
  const codeRef = useRef(null)

  useEffect(() => {
    if (created) codeRef.current?.focus()
  }, [created])

  async function handleCreate() {
    setError(null)
    setCopied(false)
    setCreating(true)
    try {
      const invitation = await createInvitation(role)
      setCreated(invitation)
      onCreated?.()
    } catch (err) {
      setError(getApiErrorMessage(err, 'We could not create the invitation. Please try again.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(created.code)
      setCopied(true)
    } catch {
      setCopied(false)
      setError('Copying is not available here. Please read or write the code down instead.')
    }
  }

  return (
    <section aria-labelledby="invite-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 id="invite-heading" className="text-2xl font-semibold text-slate-900">Invite someone</h2>
      <p className="mt-2 text-lg text-slate-600">
        Create a one-time code and give it to the person you want to invite. They enter it after signing in.
      </p>

      <fieldset className="mt-5">
        <legend className="text-lg font-medium text-slate-800">Who are you inviting?</legend>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {CHOICES.map((c) => (
            <label
              key={c.value}
              className={`flex cursor-pointer gap-3 rounded-xl border p-4 focus-within:ring-2 focus-within:ring-teal-600 ${
                role === c.value ? 'border-teal-600 bg-teal-50' : 'border-slate-300 bg-white hover:border-slate-400'
              }`}
            >
              <input
                type="radio"
                name="invite-role"
                value={c.value}
                checked={role === c.value}
                onChange={() => setRole(c.value)}
                className="mt-1 h-5 w-5 accent-teal-700"
              />
              <span>
                <span className="block text-lg font-semibold text-slate-900">{c.title}</span>
                <span className="block text-base text-slate-600">{c.text}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <Button className="mt-5" onClick={handleCreate} disabled={creating}>
        {creating ? 'Creating code…' : 'Create invitation code'}
      </Button>

      <div aria-live="polite" className="mt-5 empty:mt-0">
        {error && <Alert variant="error">{error}</Alert>}
        {created && (
          <div className="rounded-2xl border-2 border-teal-600 bg-teal-50 p-5">
            <p className="text-lg font-medium text-teal-900">
              Invitation code for a {ROLE_LABELS[created.role].toLowerCase()}:
            </p>
            <p
              ref={codeRef}
              tabIndex={-1}
              className="mt-2 select-all break-all font-mono text-3xl font-bold tracking-wider text-slate-900 focus:outline-none sm:text-4xl"
              aria-label={`Invitation code ${created.code.split('').join(' ')}`}
              data-testid="invitation-code"
            >
              {created.code}
            </p>
            <p className="mt-3 text-base text-slate-700">
              Valid until <strong>{formatDateTime(created.expires_at)}</strong>. It works once, for one person.
            </p>
            <p className="mt-1 text-base font-medium text-slate-700">
              Share it only with the person you are inviting. For your safety it will not be shown again.
            </p>
            <Button variant="secondary" className="mt-4" onClick={handleCopy}>
              {copied ? 'Copied!' : 'Copy code'}
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
