import { matchPath } from 'react-router-dom'

export const APP_NAME = 'ElderCare Connect'

// Most specific patterns first: the first match wins.
const TITLES = [
  ['/', 'Home'],
  ['/login', 'Sign in'],
  ['/register', 'Create account'],
  ['/dashboard', 'My dashboard'],
  ['/notifications', 'Notifications'],
  ['/profile', 'My profile'],
  ['/profile/setup', 'Set up your profile'],
  ['/profile/edit', 'Edit your profile'],
  ['/connections', 'Family and caretakers'],
  ['/medications', 'My medicines'],
  ['/medications/new', 'Add a medicine'],
  ['/medications/history', 'Medicine history'],
  ['/medications/:medicationId/edit', 'Edit medicine'],
  ['/medications/:medicationId', 'Medicine details'],
  ['/appointments', 'Appointments'],
  ['/appointments/new', 'Add an appointment'],
  ['/appointments/:appointmentId/edit', 'Edit appointment'],
  ['/appointments/:appointmentId', 'Appointment details'],
  ['/care', 'Care dashboard'],
  ['/join', 'Enter an invitation code'],
  ['/linked', 'People I support'],
  ['/linked/:profileId/medications/history', 'Medicine history'],
  ['/linked/:profileId/medications/:medicationId', 'Medicine details'],
  ['/linked/:profileId/medications', 'Medicines'],
  ['/linked/:profileId/appointments/:appointmentId', 'Appointment details'],
  ['/linked/:profileId/appointments', 'Appointments'],
  ['/linked/:profileId', 'Profile'],
]

export function titleFor(pathname) {
  const hit = TITLES.find(([pattern]) => matchPath({ path: pattern, end: true }, pathname))
  return hit ? hit[1] : 'Page not found'
}
