import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { validateLogin } from '../auth/validation'
import AuthCard from '../components/auth/AuthCard'
import DemoAccounts from '../components/auth/DemoAccounts'
import Alert from '../components/ui/Alert'
import FormField from '../components/ui/FormField'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const { login, notice } = useAuth()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const alertRef = useRef(null)
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const submitRef = useRef(null)
  const [demoNotice, setDemoNotice] = useState(null)

  // Fill the form only; the user still has to press "Sign in" themselves.
  function handleUseDemo({ email, password, label }) {
    setForm({ email, password })
    setErrors({})
    setFormError(null)
    setDemoNotice(`${label} demo credentials filled in. Select “Sign in” to continue.`)
    submitRef.current?.focus()
  }

  useEffect(() => {
    if (formError) alertRef.current?.focus()
  }, [formError])

  const update = (field) => (e) => {
    setDemoNotice(null)
    setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError(null)
    const found = validateLogin(form)
    setErrors(found)
    const first = Object.keys(found)[0]
    if (first) {
      const target = first === 'email' ? emailRef : passwordRef
      target.current?.focus()
      return
    }
    setSubmitting(true)
    try {
      await login(form) // PublicOnlyRoute redirects once the session starts
    } catch (err) {
      setFormError(getApiErrorMessage(err, 'Unable to sign in. Please try again.'))
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
      title="Sign in"
      subtitle="Welcome back to ElderCare Connect"
      footer={
        <>
          New here?{' '}
          <Link to="/register" state={location.state} className="font-medium text-teal-700 underline-offset-2 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-5" aria-describedby={formError ? 'login-error' : undefined}>
        {notice && !formError && !demoNotice && <Alert variant="info">{notice}</Alert>}
        {demoNotice && !formError && <Alert variant="info">{demoNotice}</Alert>}
        {formError && (
          <Alert variant="error" ref={alertRef}>
            <span id="login-error">{formError}</span>
          </Alert>
        )}
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
        <div>
          <FormField
            ref={passwordRef}
            label="Password"
            type={showPassword ? 'text' : 'password'}
            name="password"
            autoComplete="current-password"
            value={form.password}
            onChange={update('password')}
            error={errors.password}
            required
          />
          <label className="mt-2 inline-flex min-h-12 items-center gap-3 text-base text-slate-700">
            <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} className="h-6 w-6 accent-teal-700" />
            Show password
          </label>
        </div>
        <button
          ref={submitRef}
          type="submit"
          disabled={submitting}
          className="min-h-14 rounded-xl bg-teal-700 px-5 py-3 text-lg font-semibold text-white shadow-sm transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <DemoAccounts onSelect={handleUseDemo} />
    </AuthCard>
  )
}
