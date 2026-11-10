import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import WorkspaceLayout from '../components/WorkspaceLayout.jsx'
import {
  createLocation,
  getAdminLocations,
  getApiErrorMessage,
} from '../services/api.js'

function QrCodesPage() {
  const [locations, setLocations] = useState([])
  const [codes, setCodes] = useState({})
  const [name, setName] = useState('')
  const [details, setDetails] = useState('')
  const [error, setError] = useState('')

  async function loadLocations() {
    const { data } = await getAdminLocations()
    setLocations(data.locations)
    const entries = await Promise.all(data.locations.map(async (location) => {
      const reportUrl = new URL('/report', window.location.origin)
      reportUrl.searchParams.set('location', location.id)
      return [location.id, await QRCode.toDataURL(reportUrl.toString(), {
        margin: 2,
        width: 256,
        color: { dark: '#192f51', light: '#ffffff' },
      })]
    }))
    setCodes(Object.fromEntries(entries))
  }

  useEffect(() => {
    Promise.resolve()
      .then(loadLocations)
      .catch((requestError) => setError(getApiErrorMessage(requestError, 'Unable to load locations.')))
  }, [])

  async function addLocation(event) {
    event.preventDefault()
    setError('')
    try {
      await createLocation({ name, details: details || null })
      setName('')
      setDetails('')
      await loadLocations()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to create location.'))
    }
  }

  function download(location) {
    const link = document.createElement('a')
    link.href = codes[location.id]
    link.download = `campusfix-location-${location.id}.png`
    link.click()
  }

  return (
    <WorkspaceLayout title="Location QR codes">
      <form className="workspace-panel workspace-form location-form" onSubmit={addLocation}>
        <h2>Create a location or asset</h2>
        <label className="form-field">
          <span>Name</span>
          <input maxLength="150" required value={name} onChange={(event) => setName(event.target.value)} placeholder="Room 204 Projector" />
        </label>
        <label className="form-field">
          <span>Details (optional)</span>
          <textarea maxLength="1000" value={details} onChange={(event) => setDetails(event.target.value)} />
        </label>
        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        <button className="auth-submit" type="submit">Add location</button>
      </form>
      <div className="qr-grid">
        {locations.map((location) => (
          <article className="workspace-panel qr-card" key={location.id}>
            <div className="qr-card__body">
              <div>
                <h2>{location.name}</h2>
                {location.details && <p>{location.details}</p>}
                <p className="eyebrow">Location #{location.id}</p>
              </div>
              {codes[location.id] && <img src={codes[location.id]} alt={`Report QR code for ${location.name}`} />}
            </div>
            <div className="qr-actions">
              <button className="secondary-button" type="button" onClick={() => download(location)}>Download PNG</button>
              <button className="secondary-button" type="button" onClick={() => window.print()}>Print</button>
            </div>
          </article>
        ))}
      </div>
    </WorkspaceLayout>
  )
}

export default QrCodesPage
