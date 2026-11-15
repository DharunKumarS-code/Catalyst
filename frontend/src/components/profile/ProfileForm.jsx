import { useEffect, useRef, useState } from 'react'
import { getApiErrorMessage, getFieldErrors } from '../../api/client'
import { PROFILE_FIELDS, toProfileForm, toProfilePayload, todayIso, validateProfile } from '../../profile/validation'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import FormField from '../ui/FormField'
import { timeZoneLabel, timeZoneOptions } from '../../utils/timezones'

const INPUT_TEXT = 'text-lg'

/**
 * Shared create/edit form. `onSubmit(payload)` must return a promise; API errors are
 * mapped back onto the matching fields.
 */
export default function ProfileForm({ initialProfile, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(() => toProfileForm(initialProfile))
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const formRef = useRef(null)
  const alertRef = useRef(null)

  useEffect(() => {
    if (formError) alertRef.current?.focus()
  }, [formError])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  function focusFirstError(found) {
    const first = PROFILE_FIELDS.find((f) => found[f])
    if (first) formRef.current?.querySelector(`[name="${first}"]`)?.focus()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError(null)
    const found = validateProfile(form)
    setErrors(found)
    if (Object.keys(found).length) {
      focusFirstError(found)
      return
    }
    setSubmitting(true)
    try {
      await onSubmit(toProfilePayload(form))
    } catch (err) {
      const fieldErrors = getFieldErrors(err)
      setErrors(fieldErrors)
      setFormError(getApiErrorMessage(err, 'Please check the highlighted fields.'))
      setSubmitting(false)
    }
  }

  const field = (name, props) => ({
    name,
    id: `profile-${name}`,
    value: form[name],
    onChange: update(name),
    error: errors[name],
    ...props,
  })

  return (
    <form ref={formRef} noValidate onSubmit={handleSubmit} className={`flex flex-col gap-8 ${INPUT_TEXT}`}>
      {formError && (
        <Alert variant="error" ref={alertRef}>
          {formError}
        </Alert>
      )}

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">About you</legend>
        <FormField {...field('full_name', { label: 'Full name', autoComplete: 'name', required: true })} />
        <FormField
          {...field('date_of_birth', {
            label: 'Date of birth (optional)',
            type: 'date',
            min: '1900-01-01',
            max: todayIso(),
            autoComplete: 'bday',
          })}
        />
        <FormField
          {...field('phone', {
            label: 'Phone number (optional)',
            type: 'tel',
            autoComplete: 'tel',
            hint: 'Include the area code, for example 020 7946 0958.',
          })}
        />
        <FormField {...field('address', { label: 'Address (optional)', multiline: true, rows: 3, autoComplete: 'street-address' })} />
        <div>
          <label htmlFor="profile-timezone" className="block text-sm font-medium text-slate-800">
            Time zone
          </label>
          <p id="profile-timezone-hint" className="mt-1 text-sm text-slate-500">
            Medication times follow this local time. We suggest the one your device uses.
          </p>
          <select
            id="profile-timezone"
            name="timezone"
            value={form.timezone}
            onChange={update('timezone')}
            aria-describedby={errors.timezone ? 'profile-timezone-hint profile-timezone-error' : 'profile-timezone-hint'}
            aria-invalid={errors.timezone ? 'true' : undefined}
            className="mt-1.5 block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-base text-slate-900 shadow-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-100"
          >
            {timeZoneOptions(form.timezone).map((z) => (
              <option key={z} value={z}>
                {timeZoneLabel(z)}
              </option>
            ))}
          </select>
          {errors.timezone && (
            <p id="profile-timezone-error" className="mt-1.5 text-sm font-medium text-rose-700">
              {errors.timezone}
            </p>
          )}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-amber-200 bg-amber-50/40 p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">Emergency contact</legend>
        <p className="-mt-2 text-base text-slate-600">Who should we contact if something happens?</p>
        <FormField {...field('emergency_contact_name', { label: 'Contact name', required: true })} />
        <FormField {...field('emergency_contact_phone', { label: 'Contact phone number', type: 'tel', required: true })} />
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">Anything else?</legend>
        <FormField
          {...field('notes', {
            label: 'Additional notes (optional)',
            multiline: true,
            rows: 4,
            hint: 'For example, preferred visiting times or how you like to be contacted.',
          })}
        />
      </fieldset>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
