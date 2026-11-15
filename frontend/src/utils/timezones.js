// IANA time-zone helpers. The browser's zone is suggested by default; the backend validates.

const FALLBACK_ZONES = [
  'UTC', 'Europe/London', 'Europe/Dublin', 'Europe/Paris', 'Europe/Berlin', 'Europe/Madrid', 'Europe/Rome',
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'America/Toronto',
  'America/Sao_Paulo', 'Asia/Kolkata', 'Asia/Dubai', 'Asia/Singapore', 'Asia/Tokyo', 'Asia/Shanghai',
  'Australia/Sydney', 'Pacific/Auckland', 'Africa/Johannesburg', 'Africa/Lagos',
]

export function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

/** Sorted list of zones, always including `current` so an existing value stays selectable. */
export function timeZoneOptions(current) {
  let zones = FALLBACK_ZONES
  try {
    if (typeof Intl.supportedValuesOf === 'function') zones = Intl.supportedValuesOf('timeZone')
  } catch {
    // keep the fallback list
  }
  const all = new Set(['UTC', ...zones])
  if (current) all.add(current)
  return [...all].sort((a, b) => a.localeCompare(b))
}

export function timeZoneLabel(zone) {
  return zone ? zone.replaceAll('_', ' ') : ''
}
