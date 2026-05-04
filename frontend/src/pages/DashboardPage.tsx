import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Home, FileText, Send, CheckCircle, Clock, Users, Settings, BarChart2 } from 'lucide-react'
import { logout } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import { Sidebar } from '../components/Sidebar'
import { StatusBadge } from '../components/StatusBadge'

const ROLE_LABELS: Record<string, string> = {
  APPLICANT: 'Applicant',
  STUDENT_AFFAIRS: 'Student Affairs',
  TRANSFER_COMMISSION: 'Transfer Commission',
  YDYO: 'Foreign Languages Office',
  DEAN_OFFICE: "Dean's Office",
  SYSTEM_ADMIN: 'IT Administrator',
}

function NavBtn({ active, onClick, icon: Icon, label }: {
  active: boolean; onClick: () => void; icon: React.ElementType; label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm transition-colors ${
        active ? 'bg-indigo-700 text-white' : 'text-indigo-200 hover:bg-indigo-800 hover:text-white'
      }`}
    >
      <Icon className="w-5 h-5 flex-shrink-0" />
      {label}
    </button>
  )
}

function ApplicantDashboardContent({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState<'overview' | 'application' | 'messages' | 'results'>('overview')

  const application = {
    id: 'APP-2024-001',
    status: 'Foreign Languages Review',
    submittedDate: '2024-11-15',
    currentUniversity: 'Ege University',
    targetDepartment: 'Computer Engineering',
    gpa: '3.8',
    steps: [
      { name: 'Application Submitted', status: 'completed', date: '2024-11-15', office: 'System' },
      { name: 'Automated Verification', status: 'completed', date: '2024-11-15', office: 'System' },
      { name: 'Student Affairs Verification', status: 'completed', date: '2024-11-16', office: 'Student Affairs' },
      { name: 'Foreign Languages Review', status: 'pending', date: null, office: 'School of Foreign Languages' },
      { name: "Dean's Approval", status: 'waiting', date: null, office: "Dean's Office" },
      { name: 'Transfer Commission Eligibility', status: 'waiting', date: null, office: 'Transfer Commission' },
      { name: 'Ranking Generation', status: 'waiting', date: null, office: 'System' },
    ],
  }

  return (
    <div className="flex flex-1 min-h-screen">
      <Sidebar userName={userName} role="Applicant" onLogout={onLogout}>
        <NavBtn active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} icon={Home} label="Overview" />
        <NavBtn active={activeTab === 'application'} onClick={() => setActiveTab('application')} icon={FileText} label="My Application" />
        <NavBtn active={activeTab === 'messages'} onClick={() => setActiveTab('messages')} icon={Send} label="Messages" />
        <NavBtn active={activeTab === 'results'} onClick={() => setActiveTab('results')} icon={CheckCircle} label="Results" />
      </Sidebar>
      <div className="flex-1 p-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-semibold text-gray-900 mb-1">IZTECH Transfer Application</h1>
          <p className="text-gray-500 text-sm mb-8">Izmir Institute of Technology</p>

          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900 mb-1">Application Status</h2>
                    <p className="text-gray-500 text-sm">Application ID: {application.id}</p>
                  </div>
                  <StatusBadge status={application.status} />
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <div><p className="text-gray-400 text-xs mb-1">Current University</p><p className="text-gray-900 text-sm">{application.currentUniversity}</p></div>
                  <div><p className="text-gray-400 text-xs mb-1">Target Department</p><p className="text-gray-900 text-sm">{application.targetDepartment}</p></div>
                  <div><p className="text-gray-400 text-xs mb-1">GPA</p><p className="text-gray-900 text-sm">{application.gpa}</p></div>
                  <div><p className="text-gray-400 text-xs mb-1">Submitted</p><p className="text-gray-900 text-sm">{application.submittedDate}</p></div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-sm p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-6">Application Progress</h2>
                <div className="space-y-4">
                  {application.steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-4">
                      <div className="mt-0.5">
                        {step.status === 'completed' ? (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        ) : step.status === 'pending' ? (
                          <Clock className="w-5 h-5 text-blue-600" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                        )}
                      </div>
                      <div className="flex-1 flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-900">{step.name}</p>
                          <p className="text-xs text-gray-400">{step.office}</p>
                        </div>
                        <StatusBadge status={step.status} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'application' && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Application Details</h2>
              <p className="text-gray-500 text-sm">Your application details and documents will appear here once submitted.</p>
            </div>
          )}

          {activeTab === 'messages' && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Messages with Student Affairs</h2>
              <p className="text-gray-500 text-sm">No messages yet.</p>
            </div>
          )}

          {activeTab === 'results' && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="text-center py-12">
                <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-gray-700 font-medium mb-2">Results Not Yet Announced</h3>
                <p className="text-gray-500 text-sm">Your application is still being processed.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StaffDashboardContent({ userName, roleLabel, icon: Icon, onLogout }: {
  userName: string; roleLabel: string; icon: React.ElementType; onLogout: () => void
}) {
  return (
    <div className="flex flex-1 min-h-screen">
      <Sidebar userName={userName} role={roleLabel} onLogout={onLogout}>
        <NavBtn active={true} onClick={() => {}} icon={Home} label="Dashboard" />
        <NavBtn active={false} onClick={() => {}} icon={Users} label="Applications" />
        <NavBtn active={false} onClick={() => {}} icon={BarChart2} label="Reports" />
        <NavBtn active={false} onClick={() => {}} icon={Settings} label="Settings" />
      </Sidebar>
      <div className="flex-1 p-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Icon className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">{roleLabel}</h1>
              <p className="text-gray-500 text-sm">Izmir Institute of Technology</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6 mb-8">
            {[
              { label: 'Pending Review', value: '—', color: 'text-yellow-600' },
              { label: 'Approved', value: '—', color: 'text-green-600' },
              { label: 'Rejected', value: '—', color: 'text-red-600' },
            ].map((stat) => (
              <div key={stat.label} className="bg-white rounded-lg shadow-sm p-6">
                <p className="text-gray-500 text-sm mb-1">{stat.label}</p>
                <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Applications</h2>
            <p className="text-gray-500 text-sm">No applications to review at this time.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { role, userName, clearAuth } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout()
    } finally {
      clearAuth()
      navigate('/login', { replace: true })
      toast.success('Logged out.')
    }
  }

  const displayName = userName ?? 'User'
  const roleLabel = ROLE_LABELS[role ?? ''] ?? role ?? 'User'

  switch (role) {
    case 'APPLICANT':
      return <ApplicantDashboardContent userName={displayName} onLogout={handleLogout} />
    case 'STUDENT_AFFAIRS':
      return <StaffDashboardContent userName={displayName} roleLabel="Student Affairs" icon={FileText} onLogout={handleLogout} />
    case 'TRANSFER_COMMISSION':
      return <StaffDashboardContent userName={displayName} roleLabel="Transfer Commission" icon={Users} onLogout={handleLogout} />
    case 'YDYO':
      return <StaffDashboardContent userName={displayName} roleLabel="Foreign Languages Office" icon={CheckCircle} onLogout={handleLogout} />
    case 'DEAN_OFFICE':
      return <StaffDashboardContent userName={displayName} roleLabel="Dean's Office" icon={BarChart2} onLogout={handleLogout} />
    case 'SYSTEM_ADMIN':
      return <StaffDashboardContent userName={displayName} roleLabel="IT Administrator" icon={Settings} onLogout={handleLogout} />
    default:
      return <StaffDashboardContent userName={displayName} roleLabel={roleLabel} icon={Home} onLogout={handleLogout} />
  }
}
