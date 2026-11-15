import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { APP_NAME, titleFor } from './routeTitles'

/**
 * Gives every route its own document title (WCAG 2.4.2) and, after client-side navigation,
 * moves focus to the main region and announces the new page, so keyboard and screen-reader
 * users are not left on a link that no longer exists. The first page load is left alone.
 */
export default function RouteAnnouncer({ mainRef }) {
  const { pathname } = useLocation()
  const [announcement, setAnnouncement] = useState('')
  const firstRender = useRef(true)

  useEffect(() => {
    const title = titleFor(pathname)
    document.title = `${title} · ${APP_NAME}`
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    mainRef.current?.focus({ preventScroll: true })
    window.scrollTo?.(0, 0)
    setAnnouncement(`${title} page`)
  }, [pathname, mainRef])

  return (
    <p className="sr-only" aria-live="polite" aria-atomic="true">
      {announcement}
    </p>
  )
}
