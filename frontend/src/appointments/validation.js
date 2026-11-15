// Mirrors backend AppointmentIn validation for immediate feedback. The backend re-validates
// (including "must be in the future" in the profile's time zone).

import { formatClockTime } from '../medications/display'
import { todayIso } from '../profile/validation'

export const APPOINTMENT_FIELDS = [
  'doctor_name',
  'specialization',
  'clinic_name',
  'clinic_address',
  'appointment_date',
  'appointment_time',
  'appointment_type',
  'reason',
  'notes',
]

export const APPOINTMENT_TYPES = ['Check-up', 'Follow-up', 'Consultation', 'Test or scan', 'Treatment', 'Other']

const LIMITS = {
  doctor_name: 100,
  specialization: 100,
  clinic_name: 150,
  clinic_address: 300,
  appointment_type: 50,
  reason: 500,
  notes: 1000,
}
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

export function emptyAppointmentForm() {
  return Object.fromEntries(APPOINTMENT_FIELDS.map((f) => [f, '']))
}

export function validateAppointment(form) {
  const errors = {}
  for (const [field, label] of [['doctor_name', 'the doctor’s name'], ['clinic_name', 'the hospital or clinic name']]) {
    const v = form[field].trim()
    if (!v) errors[field] = `Enter ${label}.`
    else if (!/\p{L}/u.test(v)) errors[field] = 'Must contain at least one letter.'
  }
  for (const [field, max] of Object.entries(LIMITS)) {
    if (!errors[field] && form[field].trim().length > max) errors[field] = `Use ${max} characters or fewer.`
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.appointment_date)) errors.appointment_date = 'Choose the appointment date.'
  else if (form.appointment_date < todayIso()) errors.appointment_date = 'Choose a date that is not in the past.'
  if (!TIME.test(form.appointment_time)) errors.appointment_time = 'Choose the appointment time.'
  return errors
}

/** Form state -> API body (empty optional fields become null). */
export function toAppointmentPayload(form) {
  const out = {}
  for (const f of APPOINTMENT_FIELDS) {
    const v = form[f].trim()
    out[f] = v || null
  }
  return out
}

export function toAppointmentForm(appt) {
  if (!appt) return emptyAppointmentForm()
  return Object.fromEntries(APPOINTMENT_FIELDS.map((f) => [f, appt[f] ?? '']))
}

/** "2026-11-20" -> "Friday 20 November 2026" without time-zone shifting. */
export function formatAppointmentDate(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export function formatAppointmentWhen(appt) {
  return `${formatAppointmentDate(appt.appointment_date)} at ${formatClockTime(appt.appointment_time)}`
}
