import Logo from '../ui/Logo'

/** Shared frame for the sign-in and registration pages. */
export default function AuthCard({ title, subtitle, children, footer, wide = false }) {
  return (
    <div className={`mx-auto w-full ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <Logo className="h-10 w-10" />
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
            {subtitle && <p className="text-sm text-slate-600">{subtitle}</p>}
          </div>
        </div>
        {children}
      </div>
      {footer && <p className="mt-6 text-center text-sm text-slate-600">{footer}</p>}
    </div>
  )
}
