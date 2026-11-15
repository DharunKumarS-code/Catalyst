import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getApiErrorMessage, getFieldErrors } from '../api/client'
import { PASSWORD_MIN_LENGTH, validateRegistration } from '../auth/validation'
import AuthCard from '../components/auth/AuthCard'
import RoleSelector from '../components/auth/RoleSelector'
import Alert from '../components/ui/Alert'
import FormField from '../components/ui/FormField'
import { useAuth } from '../hooks/useAuth'

const EMPTY = { name: '', email: '', password: '', confirmPassword: '', role: '' }
const FIELD_ORDER = ['name', 'email', 'password', 'confirmPassword', 'role']

export default function Register() {
  const { register } = useAuth()
  const location = useLocation()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const alertRef = useRef(null)
  const nameRef = useRef(null)
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const confirmRef = useRef(null)
  const roleRef = useRef(null)

  useEffect(() => {
    if (formError) alertRef.current?.focus()
  }, [formError])

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  function focusFirst(found) {
    const first = FIELD_ORDER.find((f) => found[f])
    const targets = { name: nameRef, email: emailRef, password: passwordRef, confirmPassword: confirmRef }
    if (first === 'role') roleRef.current?.querySelector('input')?.focus()
    else if (first) targets[first].current?.focus()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError(null)
    const found = validateRegistration(form)
    setErrors(found)
    if (Object.keys(found).length) {
      focusFirst(found)
      return
    }
    setSubmitting(true)
    try {
      const { name, email, password, role } = form
      await register({ name, email, password, role }) // PublicOnlyRoute redirects
    } catch (err) {
      const fieldErrors = getFieldErrors(err)
      setErrors(fieldErrors)
      setFormError(getApiErrorMessage(err, 'Please check the highlighted fields.'))
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
      wide
      title="Create your account"
      subtitle="Join ElderCare Connect in a few steps"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" state={location.state} className="font-medium text-teal-700 underline-offset-2 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-5">
        {formError && (
          <Alert variant="error" ref={alertRef}>
            {formError}
          </Alert>
        )}
        <div ref={roleRef}>
          <RoleSelector value={form.role} onChange={(role) => setForm((f) => ({ ...f, role }))} error={errors.role} />
        </div>
        <FormField ref={nameRef} label="Full name" name="name" autoComplete="name" value={form.name} onChange={update('name')} error={errors.name} required />
        <FormField
          ref={emailRef}
          label="Email address"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          value={form.email}
          onChange={update('email')}
          error={errors.email}
          required
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            ref={passwordRef}
            label="Password"
            type={showPassword ? 'text' : 'password'}
            name="password"
            autoComplete="new-password"
            hint={`At least ${PASSWORD_MIN_LENGTH} characters with upper- and lowercase letters and a number.`}
            value={form.password}
            onChange={update('password')}
            error={errors.password}
            required
          />
          <FormField
            ref={confirmRef}
            label="Confirm password"
            type={showPassword ? 'text' : 'password'}
            name="confirmPassword"
            autoComplete="new-password"
            value={form.confirmPassword}
            onChange={update('confirmPassword')}
            error={errors.confirmPassword}
            required
          />
        </div>
        <label className="-mt-2 inline-flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} className="h-4 w-4 accent-teal-700" />
          Show passwords
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-teal-700 px-4 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthCard>
  )
}
