import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getNotifications, markNotificationRead } from '../services/api.js'

function readAuth() {
  try {
    return JSON.parse(sessionStorage.getItem('campusfix.auth') ?? 'null')
  } catch {
    return null
  }
}

function WorkspaceLayout({ title, children }) {
  const auth = readAuth()
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState([])
  const [notificationError, setNotificationError] = useState('')

  useEffect(() => {
    getNotifications()
      .then(({ data }) => setNotifications(data))
      .catch(() => setNotificationError('Notifications are temporarily unavailable.'))
  }, [])

  async function markRead(id) {
    await markNotificationRead(id)
    setNotifications((items) => items.map((item) =>
      item.id === id ? { ...item, read: true } : item,
    ))
  }

  function signOut() {
    sessionStorage.removeItem('campusfix.auth')
    sessionStorage.removeItem('campusfix.student')
    navigate('/login', { replace: true })
  }

  const links = auth?.role === 'admin'
    ? [['/admin', 'Complaints'], ['/admin/qr-codes', 'QR Codes']]
    : auth?.role === 'staff'
      ? [['/staff/tasks', 'My tasks']]
      : [['/report', 'Report issue'], ['/tracking', 'My complaints']]

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <Link className="workspace-brand" to={links[0][0]}>
          <span className="brand-mark">CF</span>
          <span>CampusFix</span>
        </Link>
        <nav className="workspace-nav" aria-label="Main navigation">
          {links.map(([href, label]) => (
            <Link key={href} to={href}>{label}</Link>
          ))}
        </nav>
        <div className="workspace-account">
          <span>{auth?.name}</span>
          <button type="button" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <section className="workspace-content">
        <div className="workspace-title-row">
          <h1>{title}</h1>
          {notifications.some((item) => !item.read) && (
            <span className="notification-count">
              {notifications.filter((item) => !item.read).length} new notification(s)
            </span>
          )}
        </div>
        {notifications.length > 0 && (
          <section className="notification-list" aria-label="Notifications">
            {notifications.slice(0, 5).map((notification) => (
              <article
                className={`notification-item${notification.read ? '' : ' notification-item--new'}`}
                key={notification.id}
              >
                <span>{notification.message}</span>
                {!notification.read && (
                  <button type="button" onClick={() => markRead(notification.id)}>
                    Mark read
                  </button>
                )}
                {notificationError && (
                  <p className="form-message form-message--error" role="status">
                    {notificationError}
                  </p>
                )}
              </article>
            ))}
          </section>
        )}
        {children}
      </section>
    </main>
  )
}

export default WorkspaceLayout
