import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import PageLoader from '../ui/PageLoader'

/**
 * Renders child routes only for signed-in users (optionally limited to `roles`).
 * This is a UX guard; the backend independently enforces every permission.
 */
export default function ProtectedRoute({ roles }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'initializing') return <PageLoader label="Checking your session…" />
  if (status !== 'authenticated') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) {
    return (
      <section className="mx-auto max-w-md py-16 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Access restricted</h1>
        <p className="mt-2 text-slate-600">Your account role does not have access to this page.</p>
      </section>
    )
  }
  return <Outlet />
}
