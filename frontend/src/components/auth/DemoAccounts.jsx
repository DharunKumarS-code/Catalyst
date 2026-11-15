import { useEffect, useState } from 'react'
import { fetchDemoAccounts } from '../../api/auth'
import { ROLE_LABELS } from '../../auth/roles'
import DemoBadge from './DemoBadge'

/**
 * Lists the demo accounts the backend reports as enabled and provisioned.
 * Renders nothing when demo mode is off, so normal deployments show no demo UI.
 * Selecting an account only fills the form; the user still submits it.
 */
export default function DemoAccounts({ onSelect }) {
  const [accounts, setAccounts] = useState([])

  useEffect(() => {
    const controller = new AbortController()
    fetchDemoAccounts(controller.signal).then(
      (list) => setAccounts(list),
      () => {
        /* demo list is optional: hide the section on any error */
      },
    )
    return () => controller.abort()
  }, [])

  if (accounts.length === 0) return null

  return (
    <section aria-labelledby="demo-accounts-heading" className="mt-8 border-t border-slate-200 pt-6">
      <div className="flex items-center gap-2">
        <h2 id="demo-accounts-heading" className="text-base font-semibold text-slate-900">Demo accounts</h2>
        <DemoBadge />
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Shared accounts for trying ElderCare Connect. They contain sample data only and cannot access real user data.
      </p>
      <ul className="mt-4 flex flex-col gap-3">
        {accounts.map((account) => {
          const label = ROLE_LABELS[account.role] ?? account.role
          return (
            <li key={account.email} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-medium text-slate-900">{label}</h3>
                  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 text-sm">
                    <dt className="text-slate-500">Email</dt>
                    <dd className="break-all font-mono text-slate-800">{account.email}</dd>
                    <dt className="text-slate-500">Password</dt>
                    <dd className="font-mono text-slate-800">{account.password}</dd>
                  </dl>
                </div>
                <button
                  type="button"
                  onClick={() => onSelect({ email: account.email, password: account.password, label })}
                  aria-label={`Use ${label} demo account`}
                  className="shrink-0 rounded-lg border border-teal-700 bg-white px-3 py-2 text-sm font-medium text-teal-800 transition-colors hover:bg-teal-50"
                >
                  Use Demo Account
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
