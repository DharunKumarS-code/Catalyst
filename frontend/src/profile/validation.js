// Mirrors backend ProfileIn validation for immediate feedback. The backend re-validates.

import { browserTimeZone } from '../utils/timezones'

export const PROFILE_FIELDS = [
  'full_name',
  'date_of_birth',
  'phone',
  'address',
  'emergency_contact_name',
  'emergency_contact_phone',
  'notes',
  'timezone',
]

export const EMPTY_PROFILE = Object.fromEntries(PROFILE_FIELDS.map((f) => [f, '']))

const PHONE_CHARS = /^\+?[0-9 ()\-.]+$/

function phoneError(value, { required, label }) {
  const v = value.trim()
  if (!v) return required ? `Enter ${label}.` : null
  const digits = v.replace(/\D/g, '')
  if (!PHONE_CHARS.test(v) || digits.length < 7 || digits.length > 15) {
    return 'Enter a valid phone number with 7 to 15 digits.'
  }
  return null
}

function nameError(value, label) {
  const v = value.trim()
  if (!v) return `Enter ${label}.`
  if (v.length > 100) return 'Use 100 characters or fewer.'
  if (!/\p{L}/u.test(v)) return 'Name must contain at least one letter.'
  return null
}

export function todayIso() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function validateProfile(form) {
  const errors = {}
  const add = (field, message) => {
    if (message) errors[field] = message
  }
  add('full_name', nameError(form.full_name, 'your full name'))
  if (form.date_of_birth) {
    if (form.date_of_birth > todayIso()) errors.date_of_birth = 'Date of birth cannot be in the future.'
    else if (form.date_of_birth < '1900-01-01') errors.date_of_birth = 'Enter a date of birth after 1900.'
  }
  add('phone', phoneError(form.phone, { required: false, label: 'your phone number' }))
  if (form.address.trim().length > 300) errors.address = 'Use 300 characters or fewer.'
  add('emergency_contact_name', nameError(form.emergency_contact_name, 'an emergency contact name'))
  add('emergency_contact_phone', phoneError(form.emergency_contact_phone, { required: true, label: 'an emergency contact phone number' }))
  if (form.notes.trim().length > 1000) errors.notes = 'Use 1000 characters or fewer.'
  if (!form.timezone) errors.timezone = 'Choose your time zone.'
  return errors
}

/** Form state -> API body (empty optional fields become null). */
export function toProfilePayload(form) {
  const clean = (v) => (v.trim() ? v.trim() : null)
  return {
    full_name: form.full_name.trim(),
    date_of_birth: form.date_of_birth || null,
    phone: clean(form.phone),
    address: clean(form.address),
    emergency_contact_name: form.emergency_contact_name.trim(),
    emergency_contact_phone: form.emergency_contact_phone.trim(),
    notes: clean(form.notes),
    timezone: form.timezone,
  }
}

/** API profile -> form state. A new profile defaults to the browser's time zone. */
export function toProfileForm(profile) {
  const form = Object.fromEntries(PROFILE_FIELDS.map((f) => [f, profile?.[f] ?? '']))
  if (!form.timezone) form.timezone = browserTimeZone()
  return form
}
