import { useId, useState } from 'react'
import { getApiErrorMessage } from '../../api/client'
import { updateNotificationPreferences } from '../../api/notifications'
import Alert from '../ui/Alert'
import Button from '../ui/Button'

const MED_TIMES = [5, 10, 15, 30, 60, 120]
const APPT_TIMES = [
  [60, '1 hour'],
  [180, '3 hours'],
  [1440, '1 day'],
  [2880, '2 days'],
  [10080, '1 week'],
]

function Toggle({ label, hint, checked, onChange, disabled }) {
  const id = useId()
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-6 w-6 shrink-0 rounded border-slate-400 text-teal-700 focus:ring-teal-600"
      />
      <label htmlFor={id} className="text-lg text-slate-900">
        {label}
        {hint && <span className="block text-base text-slate-600">{hint}</span>}
      </label>
    </div>
  )
}

function Timing({ label, value, options, onChange, disabled }) {
  const id = useId()
  return (
    <div className="ml-9">
      <label htmlFor={id} className="block text-base font-medium text-slate-800">{label}</label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 block min-h-12 w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-lg text-slate-900 shadow-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-100 disabled:opacity-60"
      >
        {options.map(([v, text]) => (
          <option key={v} value={v}>{text} before</option>
        ))}
      </select>
    </div>
  )
}

/** Your own notification settings. `isElderly` shows reminder timing; supporters only control alerts they receive. */
export default function PreferencesForm({ initial, isElderly }) {
  const [prefs, setPrefs] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState(null)
  const set = (key) => (value) => setPrefs((p) => ({ ...p, [key]: value }))
  const off = !prefs.email_enabled

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    setResult(null)
    try {
      setPrefs(await updateNotificationPreferences(prefs))
      setResult({ variant: 'success', text: 'Your notification settings were saved.' })
    } catch (err) {
      setResult({ variant: 'error', text: getApiErrorMessage(err, 'Your settings could not be saved.') })
    }
    setSaving(false)
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-5">
      <Toggle label="Send me email notifications" checked={prefs.email_enabled} onChange={set('email_enabled')} />
      {isElderly ? (
        <>
          <Toggle label="Medicine reminders" hint="A reminder shortly before each dose." checked={prefs.medication_reminders} onChange={set('medication_reminders')} disabled={off} />
          <Timing
            label="Remind me"
            value={prefs.medication_reminder_minutes}
            options={MED_TIMES.map((m) => [m, `${m} minutes`])}
            onChange={set('medication_reminder_minutes')}
            disabled={off || !prefs.medication_reminders}
          />
          <Toggle label="Tell me when a dose has not been recorded" checked={prefs.missed_dose_alerts} onChange={set('missed_dose_alerts')} disabled={off} />
          <Toggle
            label="Also tell my family and caretakers"
            hint="Only people you have connected with. They are never told which medicine it was."
            checked={prefs.notify_caretakers_of_missed_doses}
            onChange={set('notify_caretakers_of_missed_doses')}
          />
          <Toggle label="Appointment reminders" checked={prefs.appointment_reminders} onChange={set('appointment_reminders')} disabled={off} />
          <Timing
            label="Remind me"
            value={prefs.appointment_reminder_minutes}
            options={APPT_TIMES}
            onChange={set('appointment_reminder_minutes')}
            disabled={off || !prefs.appointment_reminders}
          />
        </>
      ) : (
        <Toggle
          label="Alert me when someone I support has not recorded a dose"
          hint="Sent only if they have allowed it, and only while you are connected."
          checked={prefs.missed_dose_alerts}
          onChange={set('missed_dose_alerts')}
          disabled={off}
        />
      )}
      <div aria-live="polite" className="empty:hidden">
        {result && <Alert variant={result.variant}>{result.text}</Alert>}
      </div>
      <div>
        <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</Button>
      </div>
    </form>
  )
}
