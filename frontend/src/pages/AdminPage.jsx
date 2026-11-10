import { useEffect, useState } from 'react'
import WorkspaceLayout from '../components/WorkspaceLayout.jsx'
import { ComplaintCard } from '../components/ComplaintCard.jsx'
import {
  assignComplaint,
  createStaffAccount,
  getAdminComplaints,
  getAdminLocations,
  getApiErrorMessage,
  getStaff,
} from '../services/api.js'

function AdminPage() {
  const [complaints, setComplaints] = useState([])
  const [staff, setStaff] = useState([])
  const [departments, setDepartments] = useState([])
  const [assignments, setAssignments] = useState({})
  const [staffForm, setStaffForm] = useState({
    name: '',
    employee_id: '',
    department: '',
    phone: '',
    password: '',
  })
  const [error, setError] = useState('')

  async function refresh() {
    const [complaintResponse, staffResponse, locationResponse] = await Promise.all([
      getAdminComplaints(),
      getStaff(),
      getAdminLocations(),
    ])
    setComplaints(complaintResponse.data.complaints)
    setStaff(staffResponse.data.staff)
    setDepartments(locationResponse.data.locations)
  }

  useEffect(() => {
    Promise.resolve()
      .then(refresh)
      .catch((requestError) => setError(getApiErrorMessage(requestError, 'Unable to load admin data.')))
  }, [])

  async function assign(complaintId) {
    const staffId = Number(assignments[complaintId])
    if (!staffId) return
    try {
      await assignComplaint(complaintId, staffId)
      await refresh()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to assign complaint.'))
    }
  }

  async function addStaff(event) {
    event.preventDefault()
    setError('')
    try {
      await createStaffAccount(staffForm)
      setStaffForm({ name: '', employee_id: '', department: '', phone: '', password: '' })
      await refresh()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Unable to create staff account.'))
    }
  }

  return (
    <WorkspaceLayout title="Complaint administration">
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <section className="workspace-summary">
        <div><strong>{complaints.length}</strong><span>Complaints</span></div>
        <div><strong>{complaints.filter((item) => item.escalation_level > 0).length}</strong><span>Escalated</span></div>
        <div><strong>{staff.length}</strong><span>Staff accounts</span></div>
        <div><strong>{departments.length}</strong><span>QR locations</span></div>
      </section>
      <form className="workspace-panel workspace-form staff-account-form" onSubmit={addStaff}>
        <h2>Create a maintenance staff login</h2>
        {[
          ['name', 'Full name', 'text'],
          ['employee_id', 'Employee ID', 'text'],
          ['department', 'Department', 'text'],
          ['phone', 'Phone (optional)', 'tel'],
          ['password', 'Temporary password (12+ characters)', 'password'],
        ].map(([field, label, type]) => (
          <label className="form-field" key={field}>
            <span>{label}</span>
            <input
              autoComplete={field === 'password' ? 'new-password' : 'off'}
              minLength={field === 'password' ? 12 : undefined}
              required={field !== 'phone'}
              type={type}
              value={staffForm[field]}
              onChange={(event) => setStaffForm((current) => ({
                ...current,
                [field]: event.target.value,
              }))}
            />
          </label>
        ))}
        <button className="auth-submit" type="submit">Create staff account</button>
      </form>
      <div className="complaint-list">
        {complaints.map((complaint) => (
          <ComplaintCard key={complaint.id} complaint={complaint}>
            <div className="admin-complaint-actions">
              <span>Escalation level: {complaint.escalation_level}</span>
              <label className="form-field">
                <span>Assign to staff</span>
                <select
                  value={assignments[complaint.id] ?? complaint.staff_id ?? ''}
                  onChange={(event) => setAssignments((current) => ({
                    ...current,
                    [complaint.id]: event.target.value,
                  }))}
                >
                  <option value="">Select staff member</option>
                  {staff.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name} — {person.department}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondary-button" type="button" onClick={() => assign(complaint.id)}>Assign</button>
            </div>
          </ComplaintCard>
        ))}
      </div>
      {complaints.length === 0 && !error && <p className="workspace-empty">No complaints have been reported.</p>}
    </WorkspaceLayout>
  )
}

export default AdminPage
