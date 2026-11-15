import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { NOTIFICATIONS_SEEN_EVENT, getUnreadCount } from '../../api/notifications'
import { ROLES } from '../../auth/roles'
import { useAuth } from '../../hooks/useAuth'
import DemoBadge from '../auth/DemoBadge'
import RoleBadge from '../auth/RoleBadge'
import Logo from '../ui/Logo'

const SUPPORTER_NAV = [
  { to: '/care', label: 'Care dashboard' },
  { to: '/linked', label: 'People I support' },
  { to: '/join', label: 'Enter code' },
]
const ROLE_NAV = {
  [ROLES.ELDERLY]: [
    { to: '/medications', label: 'My medicines' },
    { to: '/appointments', label: 'Appointments' },
    { to: '/profile', label: 'My profile' },
    { to: '/connections', label: 'Family & caretakers' },
  ],
  [ROLES.CARETAKER]: SUPPORTER_NAV,
  [ROLES.FAMILY_MEMBER]: SUPPORTER_NAV,
}

const navLinkClass =({ isActive }) =>
  `inline-flex min-h-12 items-center rounded-md px-3 py-2 text-base font-medium transition-colors ${
    isActive ? 'bg-teal-50 text-teal-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

/** Unread count, refreshed on navigation only (no polling, which would keep a sleeping server awake). */
function useUnreadCount(enabled) {
  const { pathname } = useLocation()
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    getUnreadCount(controller.signal)
      .then((d) => setUnread(d.unread))
      .catch(() => {}) // the badge is a convenience: never surface an error for it
    return () => controller.abort()
  }, [enabled, pathname])
  useEffect(() => {
    const clear = () => setUnread(0)
    window.addEventListener(NOTIFICATIONS_SEEN_EVENT, clear)
    return () => window.removeEventListener(NOTIFICATIONS_SEEN_EVENT, clear)
  }, [])
  return enabled ? unread : 0
}

export default function Header() {
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()
  const authenticated = status === 'authenticated'
  const unread = useUnreadCount(authenticated)

  const navItems = [{ to: '/', label: 'Home' }]
  if (authenticated) {
    navItems.push({ to: '/dashboard', label: 'My dashboard' }, ...(ROLE_NAV[user.role] ?? []), {
      to: '/notifications',
      label: 'Notifications',
    })
  }

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-3 px-4 py-4 sm:px-6 lg:px-8">
        <NavLink to="/" className="flex items-center gap-3 rounded-md">
          <Logo className="h-9 w-9" />
          <span className="text-lg font-semibold text-slate-900">
            ElderCare <span className="text-teal-700">Connect</span>
          </span>
        </NavLink>

        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <nav aria-label="Primary">
            <ul className="flex flex-wrap items-center gap-1">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.to === '/' || item.to === '/dashboard'} className={navLinkClass}>
                    {item.label}
                    {item.to === '/notifications' && unread > 0 && (
                      <span className="ml-2 inline-flex min-w-7 items-center justify-center rounded-full bg-rose-700 px-2 text-base font-bold text-white">
                        {unread > 98 ? '99+' : unread}
                        <span className="sr-only"> new</span>
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {authenticated ? (
            <div className="flex items-center gap-3 border-l border-slate-200 pl-3 sm:pl-4">
              <div className="hidden text-right sm:block">
                <p className="text-base font-medium text-slate-900" data-testid="header-user-name">{user.name}</p>
                <span className="inline-flex gap-1">
                  <RoleBadge role={user.role} />
                  {user.is_demo && <DemoBadge />}
                </span>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="min-h-12 rounded-lg border border-slate-300 px-3 py-2 text-base font-medium text-slate-700 transition-colors hover:bg-slate-100"
              >
                Sign out
              </button>
            </div>
          ) : (
            status === 'anonymous' && (
              <div className="flex items-center gap-2">
                <NavLink to="/login" className={navLinkClass}>Sign in</NavLink>
                <Link to="/register" className="inline-flex min-h-12 items-center rounded-lg bg-teal-700 px-3 py-2 text-base font-medium text-white shadow-sm hover:bg-teal-800">
                  Create account
                </Link>
              </div>
            )
          )}
        </div>
      </div>
    </header>
  )
}
