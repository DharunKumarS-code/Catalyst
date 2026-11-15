import { useCallback } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { getAdherence, getTodaySchedule, listMedications } from '../../api/medications'
import { useResource } from '../../hooks/useResource'
import Alert from '../ui/Alert'
import { ButtonLink } from '../ui/Button'
import PageLoader from '../ui/PageLoader'
import AdherenceSummary from './AdherenceSummary'
import MedicationList from './MedicationList'
import TodaySchedule from './TodaySchedule'

/**
 * Today's schedule, adherence and the medication list. Used by the owner (can record
 * doses) and, read-only, by caretakers/family members (`profileId` set).
 */
export default function MedicationOverview({ profileId, canModify, medicationHref, historyHref }) {
  const loadToday = useCallback((signal) => getTodaySchedule({ profileId }, signal), [profileId])
  const loadAdherence = useCallback((signal) => getAdherence({ profileId }, signal), [profileId])
  const loadMeds = useCallback((signal) => listMedications({ profileId }, signal), [profileId])
  const today = useResource(loadToday)
  const adherence = useResource(loadAdherence)
  const meds = useResource(loadMeds)
  const { reload: reloadToday } = today
  const { reload: reloadAdherence } = adherence

  const onChanged = useCallback(() => {
    reloadToday()
    reloadAdherence()
  }, [reloadToday, reloadAdherence])

  const firstError = today.error || adherence.error || meds.error
  if (firstError && !today.data) {
    if (canModify && firstError.response?.status === 409) {
      return (
        <div className="flex flex-col items-start gap-4">
          <Alert variant="info">Create your profile first, so we know your time zone for medication times.</Alert>
          <ButtonLink to="/profile/setup">Set up my profile</ButtonLink>
        </div>
      )
    }
    return <Alert variant="error">{getApiErrorMessage(firstError, 'We could not load medications.')}</Alert>
  }
  if (!today.data || !adherence.data || !meds.data) return <PageLoader label="Loading medications…" />

  const active = meds.data.filter((m) => m.status === 'active')
  const stopped = meds.data.filter((m) => m.status !== 'active')

  return (
    <div className="flex flex-col gap-8">
      <TodaySchedule
        schedule={today.data}
        canModify={canModify}
        onChanged={onChanged}
        emptyText={active.length === 0 ? 'No medicines have been added yet.' : undefined}
      />
      <AdherenceSummary adherence={adherence.data} />

      <section aria-labelledby="meds-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="meds-heading" className="text-2xl font-semibold text-slate-900">
            Current medicines
          </h2>
          {historyHref && (
            <ButtonLink to={historyHref} variant="secondary">
              View dose history
            </ButtonLink>
          )}
        </div>
        <MedicationList medications={active} linkTo={medicationHref} emptyText="No current medicines." />
      </section>

      {stopped.length > 0 && (
        <section aria-labelledby="stopped-heading">
          <h2 id="stopped-heading" className="mb-4 text-2xl font-semibold text-slate-900">
            Stopped medicines
          </h2>
          <MedicationList medications={stopped} linkTo={medicationHref} />
        </section>
      )}
    </div>
  )
}
