import { useCallback, useId, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { getDoseHistory } from '../api/medications'
import DoseHistory from '../components/medications/DoseHistory'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

const PERIODS = [7, 14, 30, 90]

/** /medications/history (owner) and /linked/:profileId/medications/history (read-only). */
export default function MedicationHistory() {
  const { profileId } = useParams()
  const [days, setDays] = useState(7)
  const selectId = useId()
  const loader = useCallback((signal) => getDoseHistory({ profileId, days }, signal), [profileId, days])
  const { data, error } = useResource(loader)
  const backTo = profileId ? `/linked/${profileId}/medications` : '/medications'

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Dose history"
        description="Every dose that was due, and whether it was recorded as taken or missed."
        actions={
          <ButtonLink to={backTo} variant="secondary">
            Back to medicines
          </ButtonLink>
        }
      />
      <div className="mb-6 max-w-xs">
        <label htmlFor={selectId} className="block text-base font-medium text-slate-800">
          Show
        </label>
        <select
          id={selectId}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="mt-1.5 block min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-lg text-slate-900 shadow-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-100"
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              Last {p} days
            </option>
          ))}
        </select>
      </div>
      {error && <Alert variant="error">{getApiErrorMessage(error, 'We could not load the history.')}</Alert>}
      {data ? <DoseHistory doses={data} /> : !error && <PageLoader label="Loading history…" />}
    </div>
  )
}
