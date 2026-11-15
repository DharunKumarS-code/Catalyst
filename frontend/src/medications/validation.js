// Mirrors backend MedicationIn validation for immediate feedback. The backend re-validates.

import { todayIso } from '../profile/validation'

export const FREQUENCIES = [
  { value: 'once_daily', label: 'Once a day', count: 1, defaults: ['08:00'] },
  { value: 'twice_daily', label: 'Twice a day', count: 2, defaults: ['08:00', '20:00'] },
  { value: 'three_times_daily', label: 'Three times a day', count: 3, defaults: ['08:00', '14:00', '20:00'] },
  { value: 'four_times_daily', label: 'Four times a day', count: 4, defaults: ['08:00', '12:00', '16:00', '20:00'] },
]

export const FREQUENCY_LABELS = Object.fromEntries(FREQUENCIES.map((f) => [f.value, f.label]))

export const MEDICATION_FIELDS = [
  'name',
  'dosage',
  'frequency',
  'times',
  'start_date',
  'end_date',
  'instructions',
  'prescribing_doctor',
]

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

export function frequencyInfo(value) {
  return FREQUENCIES.find((f) => f.value === value) ?? FREQUENCIES[0]
}

/** Keep the times list in step with the chosen frequency, preserving what was entered. */
export function timesForFrequency(frequency, current = []) {
  const { count, defaults } = frequencyInfo(frequency)
  return Array.from({ length: count }, (_, i) => current[i] || defaults[i])
}

export function emptyMedicationForm() {
  return {
    name: '',
    dosage: '',
    frequency: 'once_daily',
    times: ['08:00'],
    start_date: todayIso(),
    end_date: '',
    instructions: '',
    prescribing_doctor: '',
  }
}

export function validateMedication(form) {
  const errors = {}
  const name = form.name.trim()
  if (!name) errors.name = 'Enter the medication name.'
  else if (name.length > 100) errors.name = 'Use 100 characters or fewer.'
  else if (!/\p{L}/u.test(name)) errors.name = 'Medication name must contain at least one letter.'

  const dosage = form.dosage.trim()
  if (!dosage) errors.dosage = 'Enter the dosage, for example 500 mg.'
  else if (dosage.length > 50) errors.dosage = 'Use 50 characters or fewer.'

  const times = form.times.map((t) => t.trim())
  const { count } = frequencyInfo(form.frequency)
  if (times.length !== count || times.some((t) => !TIME.test(t))) {
    errors.times = 'Enter every time using the 24-hour format, for example 08:00.'
  } else if (new Set(times).size !== times.length) {
    errors.times = 'Each scheduled time must be different.'
  }

  if (!form.start_date) errors.start_date = 'Choose a start date.'
  else if (form.start_date < '2000-01-01') errors.start_date = 'Enter a start date after the year 2000.'
  if (form.end_date && form.start_date && form.end_date < form.start_date) {
    errors.end_date = 'The end date cannot be before the start date.'
  }
  if (form.instructions.trim().length > 500) errors.instructions = 'Use 500 characters or fewer.'
  if (form.prescribing_doctor.trim().length > 100) errors.prescribing_doctor = 'Use 100 characters or fewer.'
  return errors
}

/** Form state -> API body (empty optional fields become null). */
export function toMedicationPayload(form) {
  const clean = (v) => (v.trim() ? v.trim() : null)
  return {
    name: form.name.trim(),
    dosage: form.dosage.trim(),
    frequency: form.frequency,
    times: [...form.times].map((t) => t.trim()).sort(),
    start_date: form.start_date,
    end_date: form.end_date || null,
    instructions: clean(form.instructions),
    prescribing_doctor: clean(form.prescribing_doctor),
  }
}

/** API medication -> form state. */
export function toMedicationForm(med) {
  if (!med) return emptyMedicationForm()
  return {
    name: med.name,
    dosage: med.dosage,
    frequency: med.frequency,
    times: timesForFrequency(med.frequency, med.times),
    start_date: med.start_date,
    end_date: med.end_date ?? '',
    instructions: med.instructions ?? '',
    prescribing_doctor: med.prescribing_doctor ?? '',
  }
}
