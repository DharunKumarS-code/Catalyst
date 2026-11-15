import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as notifApi from '../api/notifications'
import { setToken } from '../auth/tokenStorage'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDemoAccounts: vi.fn(async () => []),
}))
vi.mock('../api/portal', () => ({ fetchPortal: vi.fn(async (area) => ({ area, message: 'ok' })) }))
vi.mock('../api/health', () => ({ fetchHealth: vi.fn(() => new Promise(() => {})) }))
vi.mock('../api/notifications', () => ({
  listNotifications: vi.fn(),
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
  getNotificationStatus: vi.fn(),
  sendTestNotification: vi.fn(),
}))

const at = '2026-11-16T12:00:00+00:00'
const USERS = {
  elderly: { id: 'e1', name: 'Margaret Smith', email: 'm@example.org', role: 'elderly', is_demo: false, created_at: at },
  caretaker: { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at },
}
const PREFS = {
  email_enabled: true, medication_reminders: true, medication_reminder_minutes: 15, missed_dose_alerts: true,
  notify_caretakers_of_missed_doses: true, appointment_reminders: true, appointment_reminder_minutes: 1440,
}
const note = (over) => ({
  id: 'n1', kind: 'medication_reminder', status: 'sent', subject: 'Medicine reminder for 08:00', recipient_name: 'Margaret Smith',
  recipient_role: 'self', recipient_is_you: true, about_name: 'Margaret Smith', related_label: 'Metformin 500 mg', event_at: at,
  local_date: '2026-11-16', local_time: '08:00', timezone: 'UTC', created_at: at, sent_at: at, attempts: 1,
  failure_reason: null, delivery_note: null, ...over,
})
const apiError = (status, detail) => Object.assign(new Error('Request failed'), { response: { status, data: { detail } } })

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderAs(user) {
  setToken(fakeToken())
  authApi.fetchCurrentUser.mockResolvedValue(user)
  const ue = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/notifications']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
  return ue
}

beforeEach(() => {
  vi.clearAllMocks()
  notifApi.getNotificationStatus.mockResolvedValue({
    delivery: 'preview', smtp_configured: false, scheduler_running: true, check_interval_seconds: 60,
    missed_dose_grace_minutes: 60, last_check_at: null,
  })
  notifApi.getNotificationPreferences.mockResolvedValue(PREFS)
  notifApi.listNotifications.mockResolvedValue([
    note(),
    note({ id: 'n2', kind: 'missed_dose', status: 'failed', subject: 'Dose not yet recorded (09:00)', failure_reason: 'Could not connect to the mail server.', sent_at: null }),
    note({ id: 'n3', kind: 'missed_dose', status: 'skipped', recipient_name: 'Carl Carer', recipient_role: 'caretaker', recipient_is_you: false, delivery_note: 'Not sent: this person no longer has access.' }),
  ])
})

describe('notifications page', () => {
  it('shows preview mode clearly and the delivery status of each notification', async () => {
    renderAs(USERS.elderly)
    expect((await screen.findByText(/Preview mode:/)).closest('[role="status"]').textContent).toMatch(/not emailed/)
    const rows = await screen.findAllByTestId('notification-row')
    expect(rows.map((r) => within(r).getByTestId('notification-status').textContent)).toEqual(['✓Sent', '✕Failed', '–Not sent'])
    expect(within(rows[1]).getByText('Could not connect to the mail server.')).toBeTruthy()
    expect(within(rows[2]).getByText(/To Carl Carer \(caretaker\)/)).toBeTruthy()
    expect(within(rows[2]).getByText(/no longer has access/)).toBeTruthy()
  })

  it('lets the elderly user change reminder timing', async () => {
    notifApi.updateNotificationPreferences.mockImplementation(async (p) => p)
    const user = renderAs(USERS.elderly)
    const timing = (await screen.findAllByLabelText('Remind me'))[0]
    await user.selectOptions(timing, '30')
    await user.click(screen.getByLabelText(/Appointment reminders/))
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(notifApi.updateNotificationPreferences).toHaveBeenCalledWith({ ...PREFS, medication_reminder_minutes: 30, appointment_reminders: false })
    expect(await screen.findByText('Your notification settings were saved.')).toBeTruthy()
  })

  it('shows supporters only the alert setting they control', async () => {
    renderAs(USERS.caretaker)
    expect(await screen.findByLabelText(/has not recorded a dose/)).toBeTruthy()
    expect(screen.queryByLabelText('Remind me')).toBeNull()
    expect(screen.queryByLabelText(/Medicine reminders/)).toBeNull()
  })

  it('reports a save failure', async () => {
    notifApi.updateNotificationPreferences.mockRejectedValue(apiError(422, 'Invalid value.'))
    const user = renderAs(USERS.elderly)
    await user.click(await screen.findByRole('button', { name: 'Save settings' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Invalid value.')
  })

  it('sends a test message and refreshes the history', async () => {
    notifApi.sendTestNotification.mockResolvedValue(note({ kind: 'test', status: 'pending' }))
    const user = renderAs(USERS.elderly)
    await user.click(await screen.findByRole('button', { name: 'Send test message' }))
    expect(await screen.findByText(/Test message queued/)).toBeTruthy()
    await waitFor(() => expect(notifApi.listNotifications).toHaveBeenCalledTimes(2))
  })

  it('shows an empty history and handles load errors', async () => {
    notifApi.listNotifications.mockResolvedValue([])
    notifApi.getNotificationStatus.mockRejectedValue(apiError(503, 'Database is temporarily unavailable.'))
    renderAs(USERS.caretaker)
    expect(await screen.findByText(/No notifications yet/)).toBeTruthy()
    expect((await screen.findByRole('alert')).textContent).toContain('temporarily unavailable')
  })
})
