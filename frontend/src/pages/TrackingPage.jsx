import { useEffect, useState } from 'react'
import WorkspaceLayout from '../components/WorkspaceLayout.jsx'
import { ComplaintCard } from '../components/ComplaintCard.jsx'
import { getApiErrorMessage, getStudentComplaints, verifyComplaint } from '../services/api.js'

function TrackingPage() {
  const auth = JSON.parse(sessionStorage.getItem('campusfix.auth') ?? '{}')
  const [complaints, setComplaints] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    getStudentComplaints(auth.id)
      .then(({ data }) => setComplaints(data.complaints))
      .catch((requestError) => setError(getApiErrorMessage(requestError, 'Unable to load complaints.')))
  }, [auth.id])

  async function verify(complaintId, action) {
    try {
      await verifyComplaint(auth.id, complaintId, action)
      const { data } = await getStudentComplaints(auth.id)
      setComplaints(data.complaints)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to update verification.'))
    }
  }

  return (
    <WorkspaceLayout title="My complaints">
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      {complaints.length === 0 && !error && <p className="workspace-empty">No complaints have been submitted yet.</p>}
      <div className="complaint-list">
        {complaints.map((complaint) => (
          <ComplaintCard key={complaint.id} complaint={complaint}>
            {complaint.status === 'Resolved' && (
              <div className="verification-actions">
                <p>Is it fixed? Confirm to close, or reopen if the issue remains.</p>
                <button className="auth-submit" type="button" onClick={() => verify(complaint.id, 'confirm')}>Confirm fixed</button>
                <button className="secondary-button" type="button" onClick={() => verify(complaint.id, 'reopen')}>Reopen</button>
              </div>
            )}
          </ComplaintCard>
        ))}
      </div>
    </WorkspaceLayout>
  )
}

export default TrackingPage
