import { useEffect, useRef, useState } from 'react'
import { getApiErrorMessage, getFieldErrors } from '../../api/client'
import {
  FREQUENCIES,
  MEDICATION_FIELDS,
  timesForFrequency,
  toMedicationForm,
  toMedicationPayload,
  validateMedication,
} from '../../medications/validation'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import FormField from '../ui/FormField'

/** Shared add/edit form. `onSubmit(payload)` must return a promise. */
export default function MedicationForm({ initialMedication, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(() => toMedicationForm(initialMedication))
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const formRef = useRef(null)
  const alertRef = useRef(null)

  useEffect(() => {
    if (formError) alertRef.current?.focus()
  }, [formError])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  const setFrequency = (e) => {
    const frequency = e.target.value
    setForm((f) => ({ ...f, frequency, times: timesForFrequency(frequency, f.times) }))
  }
  const setTime = (index) => (e) =>
    setForm((f) => ({ ...f, times: f.times.map((t, i) => (i === index ? e.target.value : t)) }))

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError(null)
    const found = validateMedication(form)
    setErrors(found)
    if (Object.keys(found).length) {
      const first = MEDICATION_FIELDS.find((f) => found[f])
      formRef.current?.querySelector(`[name="${first === 'times' ? 'time-0' : first}"]`)?.focus()
      return
    }
    setSubmitting(true)
    try {
      await onSubmit(toMedicationPayload(form))
    } catch (err) {
      setErrors(getFieldErrors(err))
      setFormError(getApiErrorMessage(err, 'Please check the highlighted fields.'))
      setSubmitting(false)
    }
  }

  const field = (name, props) => ({
    name,
    id: `medication-${name}`,
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
        <legend className="px-1 text-xl font-semibold text-slate-900">Medicine</legend>
        <FormField {...field('name', { label: 'Medication name', required: true, autoComplete: 'off' })} />
        <FormField {...field('dosage', { label: 'Dosage', required: true, hint: 'For example 500 mg or 1 tablet.' })} />
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">When to take it</legend>
        <div>
          <label htmlFor="medication-frequency" className="block text-sm font-medium text-slate-800">
            How often
          </label>
          <select
            id="medication-frequency"
            name="frequency"
            value={form.frequency}
            onChange={setFrequency}
            className="mt-1.5 block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-base text-slate-900 shadow-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-100"
          >
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <fieldset aria-describedby={errors.times ? 'medication-times-error' : undefined}>
          <legend className="text-sm font-medium text-slate-800">Times (in your profile&rsquo;s time zone)</legend>
          <div className="mt-1.5 grid gap-3 sm:grid-cols-2">
            {form.times.map((time, i) => (
              <div key={i}>
                <label htmlFor={`medication-time-${i}`} className="block text-sm text-slate-600">
                  Dose {i + 1}
                </label>
                <input
                  id={`medication-time-${i}`}
                  name={`time-${i}`}
                  type="time"
                  value={time}
                  onChange={setTime(i)}
                  aria-invalid={errors.times ? 'true' : undefined}
                  className={`mt-1 block min-h-12 w-full rounded-lg border bg-white px-3.5 py-2.5 text-base text-slate-900 shadow-sm focus:outline-none focus:ring-2 ${
                    errors.times ? 'border-rose-400 focus:ring-rose-200' : 'border-slate-300 focus:border-teal-600 focus:ring-teal-100'
                  }`}
                />
              </div>
            ))}
          </div>
          {errors.times && (
            <p id="medication-times-error" className="mt-1.5 text-sm font-medium text-rose-700">
              {errors.times}
            </p>
          )}
        </fieldset>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField {...field('start_date', { label: 'Start date', type: 'date', required: true, min: '2000-01-01' })} />
          <FormField
            {...field('end_date', {
              label: 'End date (optional)',
              type: 'date',
              min: form.start_date || undefined,
              hint: 'Leave empty if there is no end date.',
            })}
          />
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <legend className="px-1 text-xl font-semibold text-slate-900">Extra details</legend>
        <FormField
          {...field('instructions', {
            label: 'Instructions (optional)',
            multiline: true,
            rows: 3,
            hint: 'For example, take with food.',
          })}
        />
        <FormField {...field('prescribing_doctor', { label: 'Prescribing doctor (optional)' })} />
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
