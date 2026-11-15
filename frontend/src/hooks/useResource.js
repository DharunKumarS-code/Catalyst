import { useCallback, useEffect, useState } from 'react'

/**
 * Load data with `loader(signal)` on mount, whenever `loader` changes, and on `reload()`.
 * `loader` must be stable (module function or useCallback). Data from the same loader
 * stays visible while reloading; switching loaders never shows the previous loader's data.
 */
export function useResource(loader) {
  const [version, setVersion] = useState(0)
  const [result, setResult] = useState({ loader: null, version: -1, data: null, error: null })

  useEffect(() => {
    const controller = new AbortController()
    loader(controller.signal).then(
      (data) => setResult({ loader, version, data, error: null }),
      (error) => {
        if (controller.signal.aborted) return
        setResult((prev) => ({ loader, version, data: prev.loader === loader ? prev.data : null, error }))
      },
    )
    return () => controller.abort()
  }, [loader, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const current = result.loader === loader
  return {
    loading: !current || result.version !== version,
    data: current ? result.data : null,
    error: current ? result.error : null,
    reload,
  }
}
