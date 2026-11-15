import { ROLE_LABELS, ROLES } from '../../auth/roles'

const STYLES = {
  [ROLES.ELDERLY]: 'bg-teal-50 text-teal-800 ring-teal-200',
  [ROLES.CARETAKER]: 'bg-sky-50 text-sky-800 ring-sky-200',
  [ROLES.FAMILY_MEMBER]: 'bg-violet-50 text-violet-800 ring-violet-200',
}

export default function RoleBadge({ role }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[role] ?? 'bg-slate-100 text-slate-700 ring-slate-200'}`}>
      {ROLE_LABELS[role] ?? role}
    </span>
  )
}
