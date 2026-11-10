import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import WorkspaceLayout from '../components/WorkspaceLayout.jsx'
import {
  analyzeComplaint,
  createComplaint,
  createComplaintWithPhoto,
  getApiErrorMessage,
  getLocations,
} from '../services/api.js'

const categories = ['Electrical', 'Plumbing', 'Furniture', 'Network', 'AV Equipment', 'Washroom', 'Other']
const priorities = ['low', 'medium', 'high', 'critical']

function ReportPage() {
  const auth = JSON.parse(sessionStorage.getItem('campusfix.auth') ?? '{}')
  const [searchParams] = useSearchParams()
  const [locations, setLocations] = useState([])
  const [form, setForm] = useState({
    title: '',
    description: '',
    location: '',
    category: 'Other',
    priority: 'medium',
    suggested_team: '',
    summary: '',
  })
  const [photo, setPhoto] = useState(null)
  const [suggested, setSuggested] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getLocations()
      .then(({ data }) => {
        setLocations(data)
        const selected = data.find((location) => String(location.id) === searchParams.get('location'))
        if (selected) setForm((current) => ({ ...current, location: selected.name }))
      })
      .catch(() => setLocations([]))
  }, [searchParams])

  function updateField(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  async function requestSuggestion() {
    setError('')
    setBusy(true)
    try {
      const { data } = await analyzeComplaint(form.title, form.description, photo)
      setForm((current) => ({ ...current, ...data }))
      setSuggested(true)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to analyze this complaint.'))
    } finally {
      setBusy(false)
    }
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      let complaint = form
      if (!suggested) {
        const { data } = await analyzeComplaint(form.title, form.description, photo)
        complaint = { ...form, ...data }
        setForm(complaint)
        setSuggested(true)
      }
      if (photo) {
        await createComplaintWithPhoto(auth.id, complaint, photo)
      } else {
        await createComplaint(auth.id, complaint)
      }
      setMessage('Your complaint has been submitted.')
      setForm({
        title: '',
        description: '',
        location: '',
        category: 'Other',
        priority: 'medium',
        suggested_team: '',
        summary: '',
      })
      setPhoto(null)
      setSuggested(false)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to submit your complaint.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <WorkspaceLayout title="Report a maintenance issue">
      <form className="workspace-panel workspace-form" onSubmit={submit}>
        <label className="form-field">
          <span>Issue title</span>
          <input name="title" maxLength="200" required value={form.title} onChange={updateField} />
        </label>
        <label className="form-field">
          <span>Description</span>
          <textarea name="description" maxLength="10000" required value={form.description} onChange={updateField} />
        </label>
        <label className="form-field">
          <span>Location</span>
          {locations.length > 0 ? (
            <select name="location" required value={form.location} onChange={updateField}>
              <option value="">Select a campus location</option>
              {locations.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
            </select>
          ) : (
            <input name="location" required value={form.location} onChange={updateField} placeholder="Building and room" />
          )}
        </label>
        <label className="form-field">
          <span>Before photo (optional, JPEG/PNG/WebP, max 8 MB)</span>
          <input accept="image/jpeg,image/png,image/webp" type="file" onChange={(event) => {
            setPhoto(event.target.files?.[0] ?? null)
            setSuggested(false)
          }} />
        </label>
        <button className="secondary-button" disabled={busy || !form.title || !form.description} type="button" onClick={requestSuggestion}>
          {busy ? 'Analyzing…' : 'Suggest category and priority'}
        </button>
        {suggested && (
          <section className="suggestion-panel" aria-label="AI suggestions">
            <p>AI suggestions — review and adjust before submitting.</p>
            <label className="form-field">
              <span>Category</span>
              <select name="category" value={form.category} onChange={updateField}>
                {categories.map((category) => <option key={category}>{category}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span>Priority</span>
              <select name="priority" value={form.priority} onChange={updateField}>
                {priorities.map((priority) => <option key={priority}>{priority}</option>)}
              </select>
            </label>
            <label className="form-field">
              <span>Suggested team</span>
              <input name="suggested_team" value={form.suggested_team} onChange={updateField} />
            </label>
            <label className="form-field">
              <span>Summary</span>
              <textarea name="summary" value={form.summary} onChange={updateField} />
            </label>
          </section>
        )}
        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        {message && <p className="form-message form-message--success" role="status">{message}</p>}
        <button className="auth-submit" disabled={busy} type="submit">{busy ? 'Submitting…' : 'Submit complaint'}</button>
      </form>
    </WorkspaceLayout>
  )
}

export default ReportPage
