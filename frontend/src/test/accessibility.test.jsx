import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axe from 'axe-core'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as careApi from '../api/care'
import { clearToken, setToken } from '../auth/tokenStorage'
import { titleFor } from '../components/layout/routeTitles'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDemoAccounts: vi.fn(async () => []),
}))
vi.mock('../api/portal', () => ({ fetchPortal: vi.fn(async (area) => ({ area, message: 'ok' })) }))
vi.mock('../api/health', () => ({ fetchHealth: vi.fn(() => new Promise(() => {})) }))
vi.mock('../api/care', () => ({ getCareDashboard: vi.fn() }))
vi.mock('../api/notifications', async (orig) => ({
  ...(await orig()),
  getUnreadCount: vi.fn(async () => ({ unread: 0 })),
}))

const at = '2026-11-16T12:00:00+00:00'
const CARETAKER = { id: 'c1', name: 'Carl Carer', email: 'c@example.org', role: 'caretaker', is_demo: false, created_at: at }

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderApp(path) {
  const user = userEvent.setup()
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
  return { user, ...view }
}

// jsdom has no layout engine, so colour contrast is checked separately in a real browser.
async function axeViolations(container) {
  const result = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } })
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)
}

beforeEach(() => {
  vi.clearAllMocks()
  clearToken()
})

describe('automated accessibility checks (axe-core)', () => {
  it.each([
    ['/', 'heading', /Medicines, appointments and family care/],
    ['/login', 'heading', 'Sign in'],
    ['/register', 'heading', 'Create your account'],
  ])('%s has no axe violations', async (path, role, name) => {
    const { container } = renderApp(path)
    await screen.findByRole(role, { name })
    expect(await axeViolations(container)).toEqual([])
  })

  it('the care dashboard has no axe violations', async () => {
    setToken(fakeToken())
    authApi.fetchCurrentUser.mockResolvedValue(CARETAKER)
    careApi.getCareDashboard.mockResolvedValue({ generated_at: at, profiles: [] })
    const { container } = renderApp('/care')
    await screen.findByRole('heading', { name: 'Care dashboard' })
    expect(await axeViolations(container)).toEqual([])
  })
})

describe('landing page', () => {
  it('explains all three roles and offers sign-in and registration, with no unfinished-feature notes', async () => {
    renderApp('/')
    for (const role of ['Elderly individuals', 'Caretakers', 'Family members']) {
      expect(await screen.findByRole('heading', { name: role })).toBeTruthy()
    }
    expect(screen.getByRole('link', { name: 'Create an account' }).getAttribute('href')).toBe('/register')
    expect(screen.getAllByRole('link', { name: 'Sign in' }).length).toBeGreaterThan(0)
    expect(document.body.textContent).not.toMatch(/later phase|Phase \d|connectivity/i)
  })
})

describe('route titles and focus management', () => {
  it('maps routes to page titles, most specific first', () => {
    expect(titleFor('/')).toBe('Home')
    expect(titleFor('/medications/new')).toBe('Add a medicine')
    expect(titleFor('/medications/abc123')).toBe('Medicine details')
    expect(titleFor('/linked/p1/medications/history')).toBe('Medicine history')
    expect(titleFor('/nope')).toBe('Page not found')
  })

  it('sets the document title and moves focus to the main region after navigation', async () => {
    const { user } = renderApp('/')
    await screen.findByRole('heading', { name: /Medicines, appointments/ })
    expect(document.title).toBe('Home · ElderCare Connect')
    expect(document.activeElement).not.toBe(document.getElementById('main')) // first load: focus untouched

    await user.click(screen.getByRole('link', { name: 'Create an account' }))
    await screen.findByRole('heading', { name: 'Create your account' })
    await waitFor(() => expect(document.title).toBe('Create account · ElderCare Connect'))
    expect(document.activeElement).toBe(document.getElementById('main'))
  })
})
