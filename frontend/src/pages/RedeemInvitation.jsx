import { useEffect, useRef, useState } from 'react'
import { getApiErrorMessage } from '../api/client'
import { redeemInvitation } from '../api/linking'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import FormField from '../components/ui/FormField'
import PageHeader from '../components/ui/PageHeader'

const CODE_CHARS = /^[0-9A-Za-z\s-]*$/

/** Caretaker / family member: enter an invitation code to connect to an elderly profile. */
export default function RedeemInvitation() {
  const [code, setCode] = useState('')
  const [fieldError, setFieldError] = useState(null)
  const [result, setResult] = useState(null) // { variant, text, linked? }
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef(null)
  const resultRef = useRef(null)

  useEffect(() => {
    if (result) resultRef.current?.focus()
  }, [result])

  async function handleSubmit(e) {
    e.preventDefault()
    setResult(null)
    const compact = code.replace(/[\s-]/g, '')
    if (!compact) {
      setFieldError('Enter the invitation code you were given.')
      inputRef.current?.focus()
      return
    }
    if (!CODE_CHARS.test(code) || compact.length !== 16) {
      setFieldError('Invitation codes have 16 letters and numbers, like ABCD-EFGH-JKMN-PQRS.')
      inputRef.current?.focus()
      return
    }
    setFieldError(null)
    setSubmitting(true)
    try {
      const data = await redeemInvitation(code)
      setResult({ variant: 'success', text: data.message, linked: data.linked })
      setCode('')
    } catch (err) {
      setResult({ variant: 'error', text: getApiErrorMessage(err, 'We could not use this code. Please try again.') })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Connect with an invitation code"
        description="Ask the person you care for to create an invitation code for you, then enter it here."
      />
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div aria-live="polite">
          {result && (
            <div className="mb-5">
              <Alert variant={result.variant} ref={resultRef}>
                <p className="text-lg">{result.text}</p>
                {result.linked && (
                  <ButtonLink to={`/linked/${result.linked.profile_id}`} className="mt-3">
                    View {result.linked.full_name}’s profile
                  </ButtonLink>
                )}
              </Alert>
            </div>
          )}
        </div>
        <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-5 text-lg">
          <FormField
            ref={inputRef}
            label="Invitation code"
            name="code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            error={fieldError}
            hint="16 letters and numbers. Dashes and spaces are optional."
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={40}
            className="[&_input]:font-mono [&_input]:text-2xl [&_input]:tracking-widest"
            placeholder="ABCD-EFGH-JKMN-PQRS"
            required
          />
          <Button type="submit" disabled={submitting} className="self-start">
            {submitting ? 'Checking code…' : 'Connect'}
          </Button>
        </form>
      </div>
      <p className="mt-6 text-base text-slate-600">
        Codes work once and expire after a few days. After several incorrect attempts you will need to wait before
        trying again.
      </p>
    </div>
  )
}
