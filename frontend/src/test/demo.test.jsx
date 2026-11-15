import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import * as authApi from '../api/auth'
import * as portalApi from '../api/portal'
import AuthProvider from '../context/AuthProvider'

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  registerUser: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDemoAccounts: vi.fn(),
}))
vi.mock('../api/portal', () => ({
  fetchPortal: vi.fn(async (area) => ({ area, message: `Sample ${area} content.`, demo: true })),
}))
vi.mock('../api/health', () => ({ fetchHealth: vi.fn(() => new Promise(() => {})) }))

const DEMO = [
  { role: 'elderly', email: 'elderly.demo@eldercare.com', password: 'ElderDemo2026!', label: 'Elderly individual', area: 'elderly' },
  { role: 'caretaker', email: 'caretaker.demo@eldercare.com', password: 'CareDemo2026!', label: 'Caretaker', area: 'caretaker' },
  { role: 'family_member', email: 'family.demo@eldercare.com', password: 'FamilyDemo2026!', label: 'Family member', area: 'family' },
]

function fakeToken() {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256' })}.${b64({ exp: Math.floor(Date.now() / 1000) + 1800 })}.sig`
}

function renderLogin() {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
  return user
}

beforeEach(() => {
  vi.clearAllMocks()
  authApi.fetchDemoAccounts.mockResolvedValue(DEMO.map(({ role, email, password }) => ({ role, email, password })))
})

describe('demo accounts on the login page', () => {
  it('lists each demo account with role, email and password', async () => {
    renderLogin()
    const section = await screen.findByRole('region', { name: /Demo accounts/ })
    for (const d of DEMO) {
      const item = within(section).getByRole('heading', { name: d.label }).closest('li')
      expect(within(item).getByText(d.email)).toBeTruthy()
      expect(within(item).getByText(d.password)).toBeTruthy()
      expect(within(item).getByRole('button', { name: `Use ${d.label} demo account` })).toBeTruthy()
    }
    expect(within(section).getByText(/sample data only/i)).toBeTruthy()
  })

  it('fills the form without signing in, and moves focus to the Sign in button', async () => {
    const user = renderLogin()
    await user.click(await screen.findByRole('button', { name: 'Use Caretaker demo account' }))

    expect(screen.getByLabelText('Email address').value).toBe('caretaker.demo@eldercare.com')
    expect(screen.getByLabelText('Password').value).toBe('CareDemo2026!')
    expect(authApi.loginUser).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('status').textContent).toContain('Caretaker demo credentials filled in')
  })

  it.each(DEMO)('signs in as the $label demo account after an explicit click', async (d) => {
    authApi.loginUser.mockResolvedValue({
      access_token: fakeToken(),
      token_type: 'bearer',
      expires_in: 1800,
      user: { id: d.role, name: `Demo ${d.label}`, email: d.email, role: d.role, is_demo: true, created_at: '2026-11-15T00:00:00+00:00' },
    })
    const user = renderLogin()
    await user.click(await screen.findByRole('button', { name: `Use ${d.label} demo account` }))
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: `Hello, Demo ${d.label}` })).toBeTruthy()
    expect(authApi.loginUser).toHaveBeenCalledWith({ email: d.email, password: d.password })
    expect(screen.getByRole('note').textContent).toContain('You are using a demo account.')
    expect(screen.getAllByText('Demo').length).toBeGreaterThan(0)
    expect(portalApi.fetchPortal).toHaveBeenCalledWith(d.area, expect.anything())
    expect(await screen.findByText(`Sample ${d.area} content.`)).toBeTruthy()
  })

  it('hides the section when demo mode is disabled', async () => {
    authApi.fetchDemoAccounts.mockResolvedValue([])
    renderLogin()
    await screen.findByRole('heading', { name: 'Sign in' })
    await Promise.resolve()
    expect(screen.queryByRole('region', { name: /Demo accounts/ })).toBeNull()
    expect(screen.queryByText(/demo\.demo|eldercare\.com/)).toBeNull()
  })

  it('hides the section if the demo list cannot be loaded', async () => {
    authApi.fetchDemoAccounts.mockRejectedValue(new Error('network'))
    renderLogin()
    await screen.findByRole('heading', { name: 'Sign in' })
    expect(screen.queryByRole('region', { name: /Demo accounts/ })).toBeNull()
  })

  it('does not show the demo badge for regular accounts', async () => {
    authApi.fetchDemoAccounts.mockResolvedValue([])
    authApi.loginUser.mockResolvedValue({
      access_token: fakeToken(),
      token_type: 'bearer',
      expires_in: 1800,
      user: { id: 'r1', name: 'Real User', email: 'real@example.org', role: 'elderly', is_demo: false, created_at: '2026-11-15T00:00:00+00:00' },
    })
    const user = renderLogin()
    await user.type(screen.getByLabelText('Email address'), 'real@example.org')
    await user.type(screen.getByLabelText('Password'), 'RealPassword123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('heading', { name: 'Hello, Real User' })
    expect(screen.queryByRole('note')).toBeNull()
    expect(screen.queryByText('Demo')).toBeNull()
  })
})
