// Display helpers shared by the medication components.

export function doseDisplayStatus(dose) {
  if (dose.status === 'pending') return dose.is_due ? 'overdue' : 'upcoming'
  return dose.status
}

/** "08:00" -> "8:00 AM" in the viewer's locale (the clock time itself is the elderly user's local time). */
export function formatClockTime(hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export function formatPercent(value) {
  return value === null || value === undefined ? 'No doses due' : `${Math.round(value)}%`
}
