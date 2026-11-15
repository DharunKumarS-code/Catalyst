import { useCallback, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import {
  deleteMedication,
  discontinueMedication,
  getAdherence,
  getDoseHistory,
  getMedication,
} from '../api/medications'
import DemoBadge from '../components/auth/DemoBadge'
import AdherenceSummary from '../components/medications/AdherenceSummary'
import DoseHistory from '../components/medications/DoseHistory'
import Alert from '../components/ui/Alert'
import Button, { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'
import { formatClockTime } from '../medications/display'
import { FREQUENCY_LABELS } from '../medications/validation'
import { formatCalendarDate, formatDateTime } from '../utils/format'

const HISTORY_DAYS = 14

function Item({ label, children }) {
  return (
    <div className="border-b border-slate-100 py-3 last:border-b-0 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-base font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 whitespace-pre-line break-words text-lg text-slate-900 sm:col-span-2 sm:mt-0">
        {children || <span className="text-slate-400">Not provided</span>}
      </dd>
    </div>
  )
}

/**
 * /medications/:medicationId (owner: can edit, stop, delete) and
 * /linked/:profileId/medications/:medicationId (caretaker/family: read-only).
 */
export default function MedicationDetail() {
  const { medicationId, profileId } = useParams()
  const canModify = !profileId
  const navigate = useNavigate()
  const { state } = useLocation()
  const [confirming, setConfirming] = useState(null) // 'stop' | 'delete' | null
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState(null)

  const loadMed = useCallback((s) => getMedication(medicationId, { profileId }, s), [medicationId, profileId])
  const loadAdherence = useCallback((s) => getAdherence({ profileId, medicationId }, s), [medicationId, profileId])
  const loadHistory = useCallback(
    (s) => getDoseHistory({ profileId, medicationId, days: HISTORY_DAYS }, s),
    [medicationId, profileId],
  )
  const med = useResource(loadMed)
  const adherence = useResource(loadAdherence)
  const history = useResource(loadHistory)
  const backTo = canModify ? '/medications' : `/linked/${profileId}/medications`

  if (med.loading && !med.data) return <PageLoader label="Loading medication…" />
  if (med.error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {med.error.response?.status === 404
            ? 'This medication is not available. It may have been deleted, or your access may have been removed.'
            : getApiErrorMessage(med.error, 'We could not load this medication.')}
        </Alert>
        <ButtonLink to={backTo} variant="secondary" className="mt-4">
          Back to medicines
        </ButtonLink>
      </div>
    )
  }

  const m = med.data
  const active = m.status === 'active'

  async function run(action) {
    setBusy(true)
    setActionError(null)
    try {
      if (action === 'stop') {
        await discontinueMedication(m.id)
        setConfirming(null)
        med.reload()
        history.reload()
        adherence.reload()
      } else {
        await deleteMedication(m.id)
        navigate('/medications', { replace: true, state: { notice: `${m.name} was deleted.` } })
        return
      }
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'That did not work. Please try again.'))
    }
    setBusy(false)
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            {m.name}
            {!active && <span className="rounded-full bg-slate-200 px-3 py-1 text-base font-semibold text-slate-800">Stopped</span>}
            {m.is_demo && <DemoBadge />}
          </span>
        }
        description={m.dosage}
        actions={
          <>
            <ButtonLink to={backTo} variant="secondary">
              Back to medicines
            </ButtonLink>
            {canModify && active && <ButtonLink to={`/medications/${m.id}/edit`}>Edit</ButtonLink>}
          </>
        }
      />

      {state?.notice && (
        <div className="mb-6">
          <Alert variant="success">{state.notice}</Alert>
        </div>
      )}
      {actionError && (
        <div className="mb-6">
          <Alert variant="error">{actionError}</Alert>
        </div>
      )}

      <div className="flex flex-col gap-8">
        <section aria-labelledby="details-heading" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="details-heading" className="text-2xl font-semibold text-slate-900">Details</h2>
          <dl className="mt-2">
            <Item label="How often">{FREQUENCY_LABELS[m.frequency]}</Item>
            <Item label="Times">{m.times.map(formatClockTime).join(', ')}</Item>
            <Item label="Start date">{formatCalendarDate(m.start_date)}</Item>
            <Item label="End date">{m.end_date ? formatCalendarDate(m.end_date) : 'No end date'}</Item>
            <Item label="Instructions">{m.instructions}</Item>
            <Item label="Prescribing doctor">{m.prescribing_doctor}</Item>
            {!active && <Item label="Stopped on">{formatDateTime(m.discontinued_at)}</Item>}
          </dl>
        </section>

        {adherence.data && <AdherenceSummary adherence={adherence.data} />}

        <section aria-labelledby="history-heading">
          <h2 id="history-heading" className="mb-4 text-2xl font-semibold text-slate-900">
            Last {HISTORY_DAYS} days
          </h2>
          {history.error && <Alert variant="error">{getApiErrorMessage(history.error)}</Alert>}
          {history.data ? <DoseHistory doses={history.data} showMedication={false} /> : !history.error && <PageLoader label="Loading history…" />}
        </section>

        {canModify && (
          <section aria-labelledby="manage-heading" className="rounded-2xl border border-rose-200 bg-rose-50/40 p-6">
            <h2 id="manage-heading" className="text-2xl font-semibold text-slate-900">Stop or delete</h2>
            {confirming ? (
              <div role="group" aria-label="Confirm" className="mt-3 flex flex-col gap-3">
                <p className="text-lg text-slate-800">
                  {confirming === 'stop'
                    ? `Stop ${m.name}? Upcoming doses will be cancelled. Your recorded history is kept.`
                    : `Delete ${m.name} and all of its dose history? This cannot be undone.`}
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button variant="danger" disabled={busy} onClick={() => run(confirming)}>
                    {busy ? 'Working…' : confirming === 'stop' ? 'Yes, stop it' : 'Yes, delete it'}
                  </Button>
                  <Button variant="secondary" disabled={busy} onClick={() => setConfirming(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-3">
                {active && (
                  <Button variant="secondary" onClick={() => setConfirming('stop')}>
                    Stop taking this medicine
                  </Button>
                )}
                <Button variant="danger" onClick={() => setConfirming('delete')}>
                  Delete medication
                </Button>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
