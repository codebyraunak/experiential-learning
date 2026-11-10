import { useCallback, useEffect, useState } from 'react'
import WorkspaceLayout from '../components/WorkspaceLayout.jsx'
import { ComplaintCard } from '../components/ComplaintCard.jsx'
import {
  getApiErrorMessage,
  getStaffTasks,
  resolveStaffTask,
  updateStaffTaskStatus,
} from '../services/api.js'

function StaffTasksPage() {
  const auth = JSON.parse(sessionStorage.getItem('campusfix.auth') ?? '{}')
  const [tasks, setTasks] = useState([])
  const [photos, setPhotos] = useState({})
  const [notes, setNotes] = useState({})
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    const { data } = await getStaffTasks(auth.id)
    setTasks(data.tasks)
  }, [auth.id])

  useEffect(() => {
    Promise.resolve()
      .then(refresh)
      .catch((requestError) => setError(getApiErrorMessage(requestError, 'Unable to load tasks.')))
  }, [refresh])

  async function updateStatus(task, status) {
    try {
      await updateStaffTaskStatus(auth.id, task.id, status)
      await refresh()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to update task.'))
    }
  }

  async function resolve(task) {
    const photo = photos[task.id]
    const note = notes[task.id]?.trim()
    if (!photo || !note) {
      setError('Add an after photo and resolution note before marking the task resolved.')
      return
    }
    try {
      await resolveStaffTask(auth.id, task.id, photo, note)
      await refresh()
      setError('')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to resolve task.'))
    }
  }

  return (
    <WorkspaceLayout title="My maintenance tasks">
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <div className="complaint-list">
        {tasks.map((task) => (
          <ComplaintCard key={task.id} complaint={task}>
            {task.status !== 'Closed' && task.status !== 'Resolved' && (
              <div className="task-actions">
                <button className="secondary-button" type="button" onClick={() => updateStatus(task, 'In Progress')}>Start / continue work</button>
                <label className="form-field">
                  <span>After photo</span>
                  <input accept="image/jpeg,image/png,image/webp" type="file" onChange={(event) => {
                    setPhotos((current) => ({ ...current, [task.id]: event.target.files?.[0] }))
                  }} />
                </label>
                <label className="form-field">
                  <span>Resolution note</span>
                  <textarea maxLength="2000" value={notes[task.id] ?? ''} onChange={(event) => {
                    setNotes((current) => ({ ...current, [task.id]: event.target.value }))
                  }} />
                </label>
                <button className="auth-submit" type="button" onClick={() => resolve(task)}>Mark resolved</button>
              </div>
            )}
          </ComplaintCard>
        ))}
      </div>
      {tasks.length === 0 && !error && <p className="workspace-empty">No assigned tasks.</p>}
    </WorkspaceLayout>
  )
}

export default StaffTasksPage
