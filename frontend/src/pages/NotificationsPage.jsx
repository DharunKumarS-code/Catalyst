import { useState } from 'react'
import { getApiErrorMessage } from '../api/client'
import {
  getNotificationPreferences,
  getNotificationStatus,
  listNotifications,
  sendTestNotification,
} from '../api/notifications'
import { ROLES } from '../auth/roles'
import NotificationStatusBadge from '../components/notifications/NotificationStatusBadge'
import PreferencesForm from '../components/notifications/PreferencesForm'
import Alert from '../components/ui/Alert'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useAuth } from '../hooks/useAuth'
import { useResource } from '../hooks/useResource'
import { formatDateTime } from '../utils/format'

const KIND_LABELS = {
  medication_reminder: 'Medicine reminder',
  missed_dose: 'Dose not recorded',
  appointment_reminder: 'Appointment reminder',
  test: 'Test message',
}

function recipientText(n) {
  if (n.recipient_is_you) return 'To you'
  return `To ${n.recipient_name} (${n.recipient_role === 'family_member' ? 'family member' : n.recipient_role})`
}

function History({ items }) {
  if (items.length === 0) {
    return <p className="text-lg text-slate-600">No notifications yet. Reminders appear here as they are sent.</p>
  }
  return (
    <ul className="flex flex-col gap-3">
      {items.map((n) => (
        <li key={n.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="notification-row">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-teal-800">{KIND_LABELS[n.kind] ?? n.kind}</p>
              <p className="break-words text-lg font-semibold text-slate-900">{n.subject}</p>
              <p className="text-base text-slate-700">
                {recipientText(n)}
                {n.related_label && <> &middot; {n.related_label}</>}
                {n.about_name && n.recipient_role !== 'self' && <> &middot; about {n.about_name}</>}
              </p>
              <p className="text-sm text-slate-500">
                Created {formatDateTime(n.created_at)}
                {n.sent_at && <> &middot; sent {formatDateTime(n.sent_at)}</>}
              </p>
            </div>
            <NotificationStatusBadge status={n.status} />
          </div>
          {(n.failure_reason || n.delivery_note) && (
            <p className={`mt-3 text-base ${n.status === 'failed' || n.status === 'pending' ? 'text-rose-800' : 'text-slate-600'}`}>
              {n.status === 'pending' && n.failure_reason ? `Will retry: ${n.failure_reason}` : n.failure_reason || n.delivery_note}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

/** /notifications: delivery status, your settings, a test message and notification history. */
export default function NotificationsPage() {
  const { user } = useAuth()
  const status = useResource(getNotificationStatus)
  const prefs = useResource(getNotificationPreferences)
  const history = useResource(listNotifications)
  const [testState, setTestState] = useState(null)
  const [sending, setSending] = useState(false)

  async function sendTest() {
    setSending(true)
    setTestState(null)
    try {
      await sendTestNotification()
      setTestState({ variant: 'success', text: 'Test message queued. Its delivery status is shown in the history below.' })
    } catch (err) {
      setTestState({ variant: 'error', text: getApiErrorMessage(err, 'The test message could not be queued.') })
    }
    setSending(false)
    history.reload()
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Notifications"
        description="Reminders for medicines and appointments, and alerts when a dose has not been recorded."
      />

      <section aria-labelledby="delivery-heading" className="mb-8">
        <h2 id="delivery-heading" className="sr-only">Delivery status</h2>
        {status.error && <Alert variant="error">{getApiErrorMessage(status.error, 'Could not load the delivery status.')}</Alert>}
        {status.data && (
          <div
            role="status"
            className={`rounded-xl border px-4 py-3 text-lg ${status.data.delivery === 'email' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-sky-300 bg-sky-50 text-sky-900'}`}
          >
            {status.data.delivery === 'email' ? (
              <><strong>Email delivery is on.</strong> Notifications are sent to {user.email}.</>
            ) : (
              <><strong>Preview mode:</strong> email is not configured on this server, so notifications are recorded below but not emailed.</>
            )}
            {user.is_demo && <span className="mt-1 block text-base">Demo accounts never receive real emails.</span>}
            <span className="mt-1 block text-base">
              {status.data.scheduler_running
                ? `Reminders are checked automatically every ${status.data.check_interval_seconds < 60 ? `${status.data.check_interval_seconds} seconds` : `${Math.round(status.data.check_interval_seconds / 60)} minute(s)`}.`
                : 'Automatic reminder checks are not running on this server.'}
            </span>
          </div>
        )}
      </section>

      <div className="grid gap-8 lg:grid-cols-5">
        <section aria-labelledby="prefs-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-3">
          <h2 id="prefs-heading" className="mb-4 text-2xl font-semibold text-slate-900">Your settings</h2>
          {prefs.error && <Alert variant="error">{getApiErrorMessage(prefs.error, 'Could not load your settings.')}</Alert>}
          {prefs.data ? <PreferencesForm initial={prefs.data} isElderly={user.role === ROLES.ELDERLY} /> : !prefs.error && <PageLoader label="Loading settings…" />}
        </section>
        <section aria-labelledby="test-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <h2 id="test-heading" className="text-2xl font-semibold text-slate-900">Check it works</h2>
          <p className="mt-2 text-lg text-slate-700">Send yourself a test message.</p>
          <Button className="mt-4" onClick={sendTest} disabled={sending}>{sending ? 'Sending…' : 'Send test message'}</Button>
          <div aria-live="polite" className="mt-4 empty:hidden">
            {testState && <Alert variant={testState.variant}>{testState.text}</Alert>}
          </div>
        </section>
      </div>

      <section aria-labelledby="history-heading" className="mt-10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="history-heading" className="text-2xl font-semibold text-slate-900">History</h2>
          <Button variant="secondary" onClick={history.reload} disabled={history.loading}>Refresh</Button>
        </div>
        {history.error && <Alert variant="error">{getApiErrorMessage(history.error, 'Could not load notification history.')}</Alert>}
        {history.data ? <History items={history.data} /> : !history.error && <PageLoader label="Loading history…" />}
      </section>
    </div>
  )
}
