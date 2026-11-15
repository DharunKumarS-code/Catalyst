import { ROLE_OPTIONS } from '../../auth/roles'

export default function RoleSelector({ value, onChange, error }) {
  const errorId = error ? 'role-error' : undefined
  return (
    <fieldset aria-describedby={errorId} aria-invalid={error ? 'true' : undefined}>
      <legend className="text-sm font-medium text-slate-800">I am joining as</legend>
      <div className="mt-2 grid gap-3 sm:grid-cols-3">
        {ROLE_OPTIONS.map((option) => {
          const checked = value === option.value
          return (
            <label
              key={option.value}
              className={`flex cursor-pointer flex-col rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-teal-600 ${
                checked ? 'border-teal-600 bg-teal-50' : 'border-slate-300 bg-white hover:border-slate-400'
              }`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name="role"
                  value={option.value}
                  checked={checked}
                  onChange={() => onChange(option.value)}
                  className="h-4 w-4 accent-teal-700"
                />
                <span className="font-medium text-slate-900">{option.label}</span>
              </span>
              <span className="mt-1 text-sm text-slate-600">{option.description}</span>
            </label>
          )
        })}
      </div>
      {error && (
        <p id={errorId} className="mt-1.5 text-sm font-medium text-rose-700">
          {error}
        </p>
      )}
    </fieldset>
  )
}
