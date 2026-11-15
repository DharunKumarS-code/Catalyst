import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchDemoAccounts } from '../api/auth'
import { apiClient } from '../api/client'

afterEach(() => vi.restoreAllMocks())

describe('fetchDemoAccounts', () => {
  it('returns the list from the backend', async () => {
    const list = [{ role: 'elderly', email: 'elderly.demo@eldercare.com', password: 'ElderDemo2026!' }]
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: list })
    await expect(fetchDemoAccounts()).resolves.toEqual(list)
    expect(apiClient.get).toHaveBeenCalledWith('/api/auth/demo-accounts', { signal: undefined })
  })

  it('treats 404 (demo mode disabled) as an empty list', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue({ response: { status: 404 } })
    await expect(fetchDemoAccounts()).resolves.toEqual([])
  })

  it('propagates other errors', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue({ response: { status: 500 } })
    await expect(fetchDemoAccounts()).rejects.toEqual({ response: { status: 500 } })
  })
})
