// Client-side validation mirrors the backend rules for fast feedback.
// The backend remains the source of truth and re-validates everything.
import { ROLE_OPTIONS } from './roles'

export const PASSWORD_MIN_LENGTH = 12
export const PASSWORD_MAX_LENGTH = 128

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const normalizeEmail = (email) => email.trim().toLowerCase()

export function passwordProblems(password) {
  const problems = []
  if (password.length < PASSWORD_MIN_LENGTH) problems.push(`at least ${PASSWORD_MIN_LENGTH} characters`)
  if (password.length > PASSWORD_MAX_LENGTH) problems.push(`no more than ${PASSWORD_MAX_LENGTH} characters`)
  if (!/[a-z]/.test(password)) problems.push('a lowercase letter')
  if (!/[A-Z]/.test(password)) problems.push('an uppercase letter')
  if (!/\d/.test(password)) problems.push('a number')
  return problems
}

function validateEmail(email) {
  const value = normalizeEmail(email)
  if (!value) return 'Enter your email address.'
  if (!EMAIL_PATTERN.test(value)) return 'Enter a valid email address, like name@example.com.'
  return null
}

export function validateLogin({ email, password }) {
  const errors = {}
  const emailError = validateEmail(email)
  if (emailError) errors.email = emailError
  if (!password) errors.password = 'Enter your password.'
  return errors
}

export function validateRegistration({ name, email, password, confirmPassword, role }) {
  const errors = {}
  const trimmed = name.trim()
  if (!trimmed) errors.name = 'Enter your full name.'
  else if (trimmed.length > 100) errors.name = 'Name must be 100 characters or fewer.'
  else if (!/\p{L}/u.test(trimmed)) errors.name = 'Name must contain at least one letter.'

  const emailError = validateEmail(email)
  if (emailError) errors.email = emailError

  const problems = passwordProblems(password)
  if (!password) errors.password = 'Create a password.'
  else if (problems.length) errors.password = `Password needs ${problems.join(', ')}.`
  else if (password.trim() !== password) errors.password = 'Password must not start or end with a space.'

  if (!errors.password && confirmPassword !== password) errors.confirmPassword = 'Passwords do not match.'

  if (!ROLE_OPTIONS.some((r) => r.value === role)) errors.role = 'Choose how you will use ElderCare Connect.'
  return errors
}
