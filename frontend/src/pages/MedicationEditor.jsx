import { useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { createMedication, getMedication, updateMedication } from '../api/medications'
import MedicationForm from '../components/medications/MedicationForm'
import Alert from '../components/ui/Alert'
import { ButtonLink } from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import { useResource } from '../hooks/useResource'

const noMedication = async () => null

/** /medications/new and /medications/:medicationId/edit */
export default function MedicationEditor() {
  const { medicationId } = useParams()
  const navigate = useNavigate()
  const loader = useCallback(
    (signal) => (medicationId ? getMedication(medicationId, {}, signal) : noMedication()),
    [medicationId],
  )
  const { loading, data: medication, error } = useResource(loader)
  const editing = Boolean(medicationId)

  if (loading) return <PageLoader label="Loading medication…" />
  if (error || (editing && medication?.status !== 'active')) {
    return (
      <div className="mx-auto max-w-2xl">
        <Alert variant="error">
          {error ? getApiErrorMessage(error, 'We could not load this medication.') : 'A stopped medication cannot be edited.'}
        </Alert>
        <ButtonLink to="/medications" variant="secondary" className="mt-4">
          Back to my medicines
        </ButtonLink>
      </div>
    )
  }

  async function handleSubmit(payload) {
    const saved = editing ? await updateMedication(medicationId, payload) : await createMedication(payload)
    navigate(editing ? `/medications/${saved.id}` : '/medications', {
      state: { notice: editing ? 'Medication updated.' : `${saved.name} was added to your medicines.` },
    })
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={editing ? `Edit ${medication.name}` : 'Add a medication'}
        description={
          editing
            ? 'Changing the schedule updates upcoming doses. Doses you already recorded are kept.'
            : 'Doses are scheduled in the time zone saved in your profile.'
        }
      />
      <MedicationForm
        initialMedication={medication}
        submitLabel={editing ? 'Save changes' : 'Add medication'}
        onSubmit={handleSubmit}
        onCancel={() => navigate(editing ? `/medications/${medicationId}` : '/medications')}
      />
    </div>
  )
}
