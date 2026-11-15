const YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-5 text-base text-slate-600 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
        <p>&copy; {YEAR} ElderCare Connect</p>
        <p>Medicines, appointments and family care</p>
      </div>
    </footer>
  )
}
