import { env } from '../../config/env'
import { useHealthStatus } from '../../hooks/useHealthStatus'
import StatusCard from '../ui/StatusCard'

function apiCard({ state, data, error }) {
  if (state === 'loading') return { variant: 'pending', label: 'Checking…', detail: null }
  if (state === 'error') return { variant: 'error', label: 'Unreachable', detail: error }
  return {
    variant: data.status === 'ok' ? 'ok' : 'warn',
    label: data.status === 'ok' ? 'Online' : 'Degraded',
    detail: `${data.app_name} v${data.version} · ${data.environment} environment`,
  }
}

function dbCard({ state, data }) {
  if (state === 'loading') return { variant: 'pending', label: 'Checking…', detail: null }
  if (state === 'error') return { variant: 'error', label: 'Unknown', detail: 'Database status is unavailable while the API is unreachable.' }
  const db = data.database ?? {}
  if (db.status === 'connected') {
    return { variant: 'ok', label: 'Connected', detail: `Database "${db.name}" responded${db.latency_ms != null ? ` in ${db.latency_ms} ms` : ''}.` }
  }
  if (db.status === 'not_configured') {
    return { variant: 'warn', label: 'Not configured', detail: db.message }
  }
  return { variant: 'error', label: 'Disconnected', detail: db.message }
}

export default function SystemStatus() {
  const health = useHealthStatus()
  const api = apiCard(health)
  const db = dbCard(health)
  const loading = health.state === 'loading'

  return (
    <section aria-labelledby="system-status-heading" aria-live="polite" aria-busy={loading}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="system-status-heading" className="text-xl font-semibold text-slate-900">System status</h2>
          <p className="text-sm text-slate-500">
            Live connectivity check against <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">{env.apiBaseUrl}</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          {health.checkedAt && (
            <span className="text-xs text-slate-500">Last checked {health.checkedAt.toLocaleTimeString()}</span>
          )}
          <button
            type="button"
            onClick={health.refresh}
            disabled={loading}
            className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? 'Checking…' : 'Check again'}
          </button>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <StatusCard title="Backend API" description="FastAPI service health" {...api} />
        <StatusCard title="Database" description="MongoDB Atlas connection" {...db} />
      </div>
    </section>
  )
}
