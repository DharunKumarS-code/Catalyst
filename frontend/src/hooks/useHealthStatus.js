import { useCallback, useEffect, useRef, useState } from 'react'
import { describeApiError } from '../api/client'
import { fetchHealth } from '../api/health'

const INITIAL = { state: 'loading', data: null, error: null, checkedAt: null }

/** Fetch health and map it to a result object; resolves to null if aborted. */
async function loadHealth(signal) {
  try {
    const data = await fetchHealth(signal)
    return { state: 'success', data, error: null, checkedAt: new Date() }
  } catch (err) {
    if (signal.aborted) return null
    return { state: 'error', data: null, error: describeApiError(err), checkedAt: new Date() }
  }
}

/**
 * Checks the backend health endpoint on mount and on demand.
 * state: 'loading' | 'success' | 'error'
 */
export function useHealthStatus() {
  const [result, setResult] = useState(INITIAL)
  const controllerRef = useRef(null)

  const start = useCallback(() => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    loadHealth(controller.signal).then((next) => next && setResult(next))
  }, [])

  const refresh = useCallback(() => {
    setResult((prev) => ({ ...prev, state: 'loading' }))
    start()
  }, [start])

  useEffect(() => {
    start()
    return () => controllerRef.current?.abort()
  }, [start])

  return { ...result, refresh }
}
