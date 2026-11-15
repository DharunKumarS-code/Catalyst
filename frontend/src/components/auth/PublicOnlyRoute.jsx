import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import PageLoader from '../ui/PageLoader'

// Only same-app paths: blocks open redirects such as "//evil.example" or "https://…".
function safeRedirect(from) {
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/dashboard'
}

/** Login/register pages: once signed in, users go back to where they were headed. */
export default function PublicOnlyRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'initializing') return <PageLoader label="Checking your session…" />
  if (status === 'authenticated') return <Navigate to={safeRedirect(location.state?.from)} replace />
  return <Outlet />
}
