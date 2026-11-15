import { useEffect, useId, useRef, useState } from 'react'
import { getApiErrorMessage, getFieldErrors } from '../../api/client'
import {
  APPOINTMENT_FIELDS,
  APPOINTMENT_TYPES,
  toAppointmentForm,
  toAppointmentPayload,
  validateAppointment,
} from '../../appointments/validation'
import { todayIso } from '../../profile/validation'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import FormField from '../ui/FormField'

/** Shared create/edit form. `onSubmit(payload)` must return a promise. */
export default function AppointmentForm({ initialAppointment, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(() => toAppointmentForm(initialAppointment))
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const formRef = useRef(null)
  const alertRef = useRef(null)
  const typesId = useId()

  useEffect(() => {
    if (formError) alertRef.current?.focus()
  }, [formError])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError(null)
    const found = validateAppointment(form)
    setErrors(found)
    if (Object.keys(found).length) {
      const first = APPOINTMENT_FIELDS.find((f) => found[f])
      formRef.current?.querySelector(`[name="${first}"]`)?.focus()
      return
    }
    setSubmitting(true)
    try {
      await onSubmit(toAppointmentPayload(form))
    } catch (err) {
      setErrors(getFieldErrors(err))
      setFormError(getApiErrorMessage(err, 'Please check the highlighted fields.'))
      setSubmitting(false)
    }
  }

  const field = (name, props) => ({
    name,
    id: `appointment-${name}`,
    value: form[name],
    onChange: update(name),
    error: errors[name],
    ...props,
  })

  return (
    <form ref={formRef} noValidate onSubmit={handleSubmit} className="flex flex-col gap-8 text-lg">
      {formError && (
        <Alert variant="error" ref={alertRef}>
          {formError}
        </Alert>
      )}

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">When</legend>
        <p className="-mt-2 text-base text-slate-600">Use the local time in the time zone saved in your profile.</p>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField {...field('appointment_date', { label: 'Date', type: 'date', required: true, min: todayIso() })} />
          <FormField {...field('appointment_time', { label: 'Time', type: 'time', required: true })} />
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">Doctor and place</legend>
        <FormField {...field('doctor_name', { label: 'Doctor’s name', required: true, autoComplete: 'off' })} />
        <FormField {...field('specialization', { label: 'Specialization (optional)', hint: 'For example cardiology.' })} />
        <FormField {...field('clinic_name', { label: 'Hospital or clinic name', required: true })} />
        <FormField {...field('clinic_address', { label: 'Hospital or clinic address (optional)', multiline: true, rows: 2 })} />
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">About the visit</legend>
        <FormField {...field('appointment_type', { label: 'Type of appointment (optional)', list: typesId, autoComplete: 'off' })} />
        <datalist id={typesId}>
          {APPOINTMENT_TYPES.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
        <FormField {...field('reason', { label: 'Reason for visit (optional)', multiline: true, rows: 2 })} />
        <FormField
          {...field('notes', {
            label: 'Additional notes (optional)',
            multiline: true,
            rows: 3,
            hint: 'For example, bring your medication list or arrange transport.',
          })}
        />
      </fieldset>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Go back
          </Button>
        )}
      </div>
    </form>
  )
}
