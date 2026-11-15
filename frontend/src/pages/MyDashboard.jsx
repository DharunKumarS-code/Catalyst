import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { fetchPortal } from '../api/portal'
import { ROLE_LABELS, ROLE_PORTAL, ROLES } from '../auth/roles'
import DemoBadge from '../components/auth/DemoBadge'
import RoleBadge from '../components/auth/RoleBadge'
import Alert from '../components/ui/Alert'
import { useAuth } from '../hooks/useAuth'

const SUPPORTER_STEPS = [
  { to: '/care', title: 'Care dashboard', text: 'Today’s medicines, adherence and appointments for everyone you support.' },
  { to: '/notifications', title: 'Alerts', text: 'Choose whether to be emailed when a dose is not recorded.' },
  { to: '/linked', title: 'People I support', text: 'See their profiles, medicines and appointments (view only).' },
  { to: '/join', title: 'Enter an invitation code', text: 'Connect with someone who has invited you.' },
]
const NEXT_STEPS = {
  [ROLES.ELDERLY]: [
    { to: '/medications', title: 'My medicines', text: 'See today’s doses, record them, and add medicines.' },
    { to: '/appointments', title: 'My appointments', text: 'Add doctor visits and see what is coming up.' },
    { to: '/notifications', title: 'Reminders & notifications', text: 'Choose when to be reminded and see what was sent.' },
    { to: '/profile', title: 'My profile', text: 'Add or update your details and emergency contact.' },
    { to: '/connections', title: 'Family & caretakers', text: 'Invite people and choose who can see your profile.' },
  ],
  [ROLES.CARETAKER]: SUPPORTER_STEPS,
  [ROLES.FAMILY_MEMBER]: SUPPORTER_STEPS,
}

function useRolePortal(role) {
  const area = ROLE_PORTAL[role]
  const [result, setResult] = useState({ area: null, data: null, error: null })

  useEffect(() => {
    if (!area) return undefined
    const controller = new AbortController()
    fetchPortal(area, controller.signal).then(
      (data) => setResult({ area, data, error: null }),
      (err) => {
        if (!controller.signal.aborted) setResult({ area, data: null, error: getApiErrorMessage(err) })
      },
    )
    return () => controller.abort()
  }, [area])

  const loading = Boolean(area) && result.area !== area
  return { ...result, loading }
}

export default function MyDashboard() {
  const { user } = useAuth()
  const portal = useRolePortal(user.role)
  const memberSince = new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: 'long' })

  return (
    <div className="flex flex-col gap-8">
      <section className="rounded-3xl bg-gradient-to-br from-teal-700 to-teal-900 px-6 py-8 text-white shadow-sm sm:px-10">
        <p className="text-base font-medium uppercase tracking-wider text-teal-100">My dashboard</p>
        <h1 className="mt-1 text-3xl font-semibold">Hello, {user.name}</h1>
        <p className="mt-2 text-teal-50">You are signed in as a {ROLE_LABELS[user.role]?.toLowerCase() ?? 'member'}.</p>
      </section>

      {user.is_demo && (
        <div role="note" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-base text-amber-900">
          <strong className="font-semibold">You are using a demo account.</strong> Everything shown is sample data, and
          demo accounts cannot access real user information. Please don’t enter personal details.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <section aria-labelledby="profile-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="profile-heading" className="text-lg font-semibold text-slate-900">Your account</h2>
          <dl className="mt-4 space-y-3 text-base">
            <div>
              <dt className="text-slate-500">Name</dt>
              <dd className="font-medium text-slate-900">{user.name}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Email</dt>
              <dd className="break-all font-medium text-slate-900">{user.email}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Role</dt>
              <dd className="mt-1 flex flex-wrap gap-1">
                <RoleBadge role={user.role} />
                {user.is_demo && <DemoBadge />}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Member since</dt>
              <dd className="font-medium text-slate-900">{memberSince}</dd>
            </div>
          </dl>
        </section>

        <section aria-labelledby="portal-heading" aria-busy={portal.loading} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <h2 id="portal-heading" className="text-lg font-semibold text-slate-900">{ROLE_LABELS[user.role]} space</h2>
          <div className="mt-4" aria-live="polite">
            {portal.loading && <p className="text-slate-500">Loading your space…</p>}
            {portal.error && <Alert variant="error">{portal.error}</Alert>}
            {portal.data && (
              <>
                <p className="text-slate-700">{portal.data.message}</p>
                <p className="mt-4 text-base text-slate-500">
                  Access to this area was verified by the server for your role.
                </p>
              </>
            )}
          </div>
        </section>
      </div>

      <section aria-labelledby="next-steps-heading">
        <h2 id="next-steps-heading" className="mb-4 text-xl font-semibold text-slate-900">What would you like to do?</h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          {(NEXT_STEPS[user.role] ?? []).map((step) => (
            <li key={step.to}>
              <Link
                to={step.to}
                className="block h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-colors hover:border-teal-600 hover:bg-teal-50"
              >
                <span className="block text-lg font-semibold text-teal-800">{step.title}</span>
                <span className="mt-1 block text-base text-slate-600">{step.text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
