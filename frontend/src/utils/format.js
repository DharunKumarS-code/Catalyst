/** "2026-11-15T10:00:00+00:00" -> "15 November 2026" in the user's locale. */
export function formatDate(isoDateTime) {
  if (!isoDateTime) return ''
  return new Date(isoDateTime).toLocaleDateString(undefined, { dateStyle: 'long' })
}

export function formatDateTime(isoDateTime) {
  if (!isoDateTime) return ''
  return new Date(isoDateTime).toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' })
}

/** Calendar date "YYYY-MM-DD" (no time zone) -> localized date without day shifting. */
export function formatCalendarDate(isoDate) {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { dateStyle: 'long' })
}
