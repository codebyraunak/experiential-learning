import { useEffect, useState, useSyncExternalStore } from 'react'
import { getComplaintPhoto } from '../services/api.js'

let clockTimestamp = new Date().getTime()
let clockTimer
const clockListeners = new Set()

function subscribeToClock(listener) {
  clockListeners.add(listener)
  if (!clockTimer) {
    clockTimer = window.setInterval(() => {
      clockTimestamp = new Date().getTime()
      clockListeners.forEach((notify) => notify())
    }, 60_000)
  }
  return () => {
    clockListeners.delete(listener)
    if (clockListeners.size === 0) {
      window.clearInterval(clockTimer)
      clockTimer = undefined
    }
  }
}

function getClockSnapshot() {
  return clockTimestamp
}

export function SlaBadge({ dueAt }) {
  const now = useSyncExternalStore(subscribeToClock, getClockSnapshot, getClockSnapshot)
  if (!dueAt) return <span className="status-badge">SLA unavailable</span>
  const remaining = new Date(dueAt).getTime() - now
  if (remaining <= 0) return <span className="status-badge status-badge--overdue">Overdue</span>
  const hours = Math.floor(remaining / 3_600_000)
  const minutes = Math.floor((remaining % 3_600_000) / 60_000)
  return <span className="status-badge">{hours}h {minutes}m left</span>
}

export function PrivatePhoto({ filename, label }) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!filename) return undefined
    let active = true
    let objectUrl = ''
    getComplaintPhoto(filename)
      .then(({ data }) => {
        if (!active) return
        objectUrl = URL.createObjectURL(data)
        setUrl(objectUrl)
      })
      .catch(() => setFailed(true))
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [filename])

  if (!filename) return null
  return (
    <figure className="complaint-photo">
      {url
        ? <img src={url} alt={label} />
        : <span>{failed ? 'Photo unavailable' : 'Loading photo…'}</span>}
      <figcaption>{label}</figcaption>
    </figure>
  )
}

export function ComplaintCard({ complaint, children }) {
  return (
    <article className="complaint-card">
      <div className="complaint-card__header">
        <div>
          <p className="eyebrow">Complaint #{complaint.id}</p>
          <h2>{complaint.title}</h2>
        </div>
        <SlaBadge dueAt={complaint.due_at} />
      </div>
      <p>{complaint.summary || complaint.description}</p>
      <div className="complaint-meta">
        <span>{complaint.category}</span>
        <span className={`priority priority--${complaint.priority}`}>{complaint.priority}</span>
        <span>{complaint.status}</span>
        <span>{complaint.location}</span>
      </div>
      <div className="complaint-photos">
        <PrivatePhoto filename={complaint.before_photo_path} label="Before" />
        <PrivatePhoto filename={complaint.after_photo_path} label="After" />
      </div>
      {complaint.resolution_note && <p className="resolution-note">{complaint.resolution_note}</p>}
      {children}
    </article>
  )
}
