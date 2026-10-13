import { useEffect, useState } from 'react';

const mockTasks = [
  {
    id: 1,
    title: 'Reset VPN access',
    description: 'Grant access to the new onboarding account.',
    status: 'in_progress',
    priority: 'high',
    assignee_name: 'A. Ngwenya',
    requester_name: 'Support Desk',
    due_date: '2026-10-15',
  },
  {
    id: 2,
    title: 'Laptop repair approval',
    description: 'Approve urgent replacement for a damaged device.',
    status: 'assigned',
    priority: 'urgent',
    assignee_name: 'L. Smith',
    requester_name: 'IT Manager',
    due_date: '2026-10-16',
  },
  {
    id: 3,
    title: 'Install software bundle',
    description: 'Deploy the standard workstation software package.',
    status: 'new',
    priority: 'medium',
    assignee_name: 'J. Patel',
    requester_name: 'Operations Lead',
    due_date: '2026-10-18',
  },
];

const API_BASE_URL = 'http://localhost:8000/api';
const API_V1_URL = `${API_BASE_URL}/v1`;
const localDate = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
const localDateTime = (value) => {
  if (!value) return '';
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

async function apiRequest(url, token, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  });
  const responseText = await response.text();
  let payload = {};
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = { detail: responseText };
    }
  }
  if (!response.ok) {
    const detail = payload.detail || Object.values(payload).flat().join(' ');
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return payload;
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('opsflow-token') || '');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tasks, setTasks] = useState(mockTasks);
  const [profile, setProfile] = useState(null);
  const [attendance, setAttendance] = useState([]);
  const [attendanceReport, setAttendanceReport] = useState(null);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [feedbackActions, setFeedbackActions] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [operationSummary, setOperationSummary] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [responseDrafts, setResponseDrafts] = useState({});
  const [feedbackForm, setFeedbackForm] = useState({
    employee: '',
    category: 'positive_recognition',
    content: '',
    feedback_date: localDate(),
  });
  const [leaveForm, setLeaveForm] = useState({
    start_date: '',
    end_date: '',
    leave_type: 'annual',
  });
  const [scheduleForm, setScheduleForm] = useState({
    employee: '',
    weekday: '0',
    start_time: '08:00',
    end_time: '16:00',
    grace_period_minutes: 10,
    effective_from: localDate(),
  });
  const [view, setView] = useState('dashboard');
  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assignee: '',
  });
  const [message, setMessage] = useState('');

  const refreshData = async (authToken) => {
    const [taskData, userData, attendanceData, leaveData, feedbackData, actionData, dashboardData, notificationData] = await Promise.all([
      apiRequest(`${API_BASE_URL}/tasks/`, authToken),
      apiRequest(`${API_V1_URL}/accounts/me/`, authToken),
      apiRequest(`${API_V1_URL}/attendance/`, authToken),
      apiRequest(`${API_V1_URL}/attendance/leave-requests/`, authToken),
      apiRequest(`${API_V1_URL}/feedback/`, authToken),
      apiRequest(`${API_V1_URL}/feedback/actions/`, authToken),
      apiRequest(`${API_V1_URL}/dashboard/employee-operations/`, authToken),
      apiRequest(`${API_BASE_URL}/notifications/`, authToken),
    ]);
    const userList = await apiRequest(`${API_BASE_URL}/users/`, authToken);
    setTasks(taskData);
    setProfile(userData);
    setAttendance(attendanceData);
    setLeaveRequests(leaveData);
    setFeedback(feedbackData);
    setFeedbackActions(actionData);
    setEmployees(userList);
    setOperationSummary(dashboardData.employees);
    setNotifications(notificationData);
  };

  const handleMarkNotificationRead = async (id) => {
    try {
      await apiRequest(`${API_BASE_URL}/notifications/${id}/`, token, {
        method: 'PATCH',
        body: JSON.stringify({ is_read: true }),
      });
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const fetchTasks = async () => {
    if (!token) return;

    try {
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  useEffect(() => {
    if (!token) {
      setTasks(mockTasks);
      return;
    }

    fetchTasks();
  }, [token]);

  const handleLogin = async (event) => {
    event.preventDefault();
    try {
      const payload = await apiRequest(`${API_BASE_URL}/auth/login/`, '', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setToken(payload.token);
      localStorage.setItem('opsflow-token', payload.token);
      setMessage('Signed in successfully.');
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleCreateTask = async (event) => {
    event.preventDefault();
    if (!token) {
      setMessage('Please sign in before creating a task.');
      return;
    }

    try {
      const payload = { ...form };
      if (!payload.assignee) delete payload.assignee;
      if (!payload.due_date) delete payload.due_date;
      await apiRequest(`${API_BASE_URL}/tasks/`, token, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setForm({ title: '', description: '', priority: 'medium', due_date: '', assignee: '' });
      setView('dashboard');
      setMessage('Task created successfully.');
      fetchTasks();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleAttendanceAction = async (action) => {
    try {
      await apiRequest(`${API_V1_URL}/attendance/${action}/`, token, {
        method: 'POST',
      });
      setMessage(action === 'check-in' ? 'Checked in successfully.' : 'Checked out successfully.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleLeaveRequest = async (event) => {
    event.preventDefault();
    try {
      await apiRequest(`${API_V1_URL}/attendance/leave-requests/`, token, {
        method: 'POST',
        body: JSON.stringify(leaveForm),
      });
      setLeaveForm({ start_date: '', end_date: '', leave_type: 'annual' });
      setMessage('Leave request submitted for review.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleLeaveReview = async (id, decision) => {
    try {
      await apiRequest(`${API_V1_URL}/attendance/leave-requests/${id}/review/`, token, {
        method: 'POST',
        body: JSON.stringify({ status: decision }),
      });
      setMessage(`Leave request ${decision}.`);
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleFeedbackCreate = async (event) => {
    event.preventDefault();
    try {
      await apiRequest(`${API_V1_URL}/feedback/`, token, {
        method: 'POST',
        body: JSON.stringify(feedbackForm),
      });
      setFeedbackForm({
        ...feedbackForm,
        employee: '',
        content: '',
      });
      setMessage('Private feedback published.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleFeedbackAcknowledgement = async (id) => {
    try {
      await apiRequest(`${API_V1_URL}/feedback/${id}/acknowledge/`, token, {
        method: 'POST',
      });
      setMessage('Feedback receipt acknowledged.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleFeedbackResponse = async (event, id) => {
    event.preventDefault();
    try {
      await apiRequest(`${API_V1_URL}/feedback/${id}/responses/`, token, {
        method: 'POST',
        body: JSON.stringify({ response: responseDrafts[id] || '' }),
      });
      setMessage('Your response was saved.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleScheduleCreate = async (event) => {
    event.preventDefault();
    try {
      await apiRequest(`${API_V1_URL}/attendance/schedules/`, token, {
        method: 'POST',
        body: JSON.stringify({
          ...scheduleForm,
          weekday: Number(scheduleForm.weekday),
          grace_period_minutes: Number(scheduleForm.grace_period_minutes),
        }),
      });
      setMessage('Work schedule saved.');
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleCreateAction = async (event, item) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      await apiRequest(`${API_V1_URL}/feedback/${item.id}/actions/`, token, {
        method: 'POST',
        body: JSON.stringify({
          title: formData.get('title'),
          due_date: formData.get('due_date') || null,
          assigned_to: Number(formData.get('assigned_to')),
        }),
      });
      setMessage('Development follow-up action created.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleActionStatus = async (id, nextStatus) => {
    try {
      await apiRequest(`${API_V1_URL}/feedback/actions/${id}/`, token, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      await refreshData(token);
      setMessage('Follow-up action updated.');
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleReport = async () => {
    try {
      const report = await apiRequest(
        `${API_V1_URL}/attendance/reports/?period=daily&date=${localDate()}`,
        token,
      );
      setAttendanceReport(report);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleAttendanceCorrection = async (event, record) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      await apiRequest(`${API_V1_URL}/attendance/${record.id}/`, token, {
        method: 'PATCH',
        body: JSON.stringify({
          check_in: formData.get('check_in') || null,
          check_out: formData.get('check_out') || null,
          status: formData.get('status'),
          is_remote: formData.get('is_remote') === 'on',
          correction_reason: formData.get('correction_reason'),
        }),
      });
      setMessage('Attendance corrected and audit history recorded.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const isManager = profile?.is_superuser || profile?.role === 'administrator' || profile?.role === 'it_manager';

  const pendingCount = tasks.filter((task) => task.status !== 'completed').length;
  const overdueCount = tasks.filter((task) => task.status !== 'completed' && task.due_date && task.due_date < localDate()).length;
  const lowPriorityCount = tasks.filter((task) => task.priority === 'low').length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">OF</div>
          <div>
            <h1>OperationsFlow</h1>
            <p>Internal IT workflow</p>
          </div>
        </div>

        <nav className="nav">
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>
            Dashboard
          </button>
          <button className={view === 'tasks' ? 'active' : ''} onClick={() => setView('tasks')}>
            Active tasks
          </button>
          <button className={view === 'new-task' ? 'active' : ''} onClick={() => setView('new-task')}>
            New task
          </button>
          {token && (
            <>
                  <button className={view === 'attendance' ? 'active' : ''} onClick={() => setView('attendance')}>
                Attendance & leave
              </button>
              <button className={view === 'feedback' ? 'active' : ''} onClick={() => setView('feedback')}>
                Feedback & development
              </button>
            </>
          )}
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Operations</p>
            <h2>Service desk overview</h2>
          </div>
          {!token ? (
            <form className="login-form" onSubmit={handleLogin}>
              <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" />
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" />
              <button type="submit">Sign in</button>
            </form>
          ) : (
            <div className="account-chip">
              <span>{profile?.username}</span>
            <button className="logout" onClick={() => { localStorage.removeItem('opsflow-token'); setToken(''); setProfile(null); setView('dashboard'); setMessage('Signed out.'); }}>
              Sign out
            </button>
            </div>
          )}
          {token && (
            <div className="panel wide-panel">
              <h3>Notifications</h3>
              {notifications.length ? notifications.slice(0, 8).map((notification) => (
                <div className={`notification-row ${notification.is_read ? 'read' : ''}`} key={notification.id}>
                  <span>{notification.message}</span>
                  {!notification.is_read && <button className="secondary" onClick={() => handleMarkNotificationRead(notification.id)}>Mark read</button>}
                </div>
              )) : <p className="muted">No notifications yet.</p>}
            </div>
          )}
        </header>

        {message && <div className="notice">{message}</div>}

        {view === 'dashboard' && (
          <section className="content-grid">
            <div className="metric-card">
              <span>Total active</span>
              <strong>{pendingCount}</strong>
            </div>
            <div className="metric-card">
              <span>Due soon / overdue</span>
              <strong>{overdueCount}</strong>
            </div>
            <div className="metric-card">
              <span>Low priority</span>
              <strong>{lowPriorityCount}</strong>
            </div>
            <div className="metric-card">
              <span>Assigned to team</span>
              <strong>{tasks.length}</strong>
            </div>

            <div className="panel wide-panel">
              <h3>Recent workflow activity</h3>
              <ul className="activity-list">
                {tasks.slice(0, 4).map((task) => (
                  <li key={task.id}>
                    <span className="pill">{task.status}</span>
                    <div>
                      <strong>{task.title}</strong>
                      <small>{task.assignee_name || 'Unassigned'} · {task.priority}</small>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            {token && (
              <div className="panel wide-panel">
                <h3>Employee operations overview</h3>
                <p className="muted">Operational context only; these figures are not performance ratings.</p>
                <div className="operations-summary">
                  {operationSummary.map((entry) => (
                    <article className="summary-item" key={entry.employee_id}>
                      <strong>{entry.employee_name}</strong>
                      <span>Tasks: {entry.task_summary.completed} completed · {entry.task_summary.active} active · {entry.task_summary.overdue} overdue</span>
                      <span>Attendance this month: {entry.attendance_month_to_date.present} present · {entry.attendance_month_to_date.late} late · {entry.attendance_month_to_date.pending_review} pending review · {entry.attendance_month_to_date.approved_leave_requests} approved leave request(s)</span>
                      <span>Follow-ups: {entry.feedback_actions.outstanding} outstanding · {entry.feedback_actions.overdue} overdue</span>
                    </article>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {view === 'tasks' && (
          <section className="panel">
            <h3>Open tasks</h3>
            <div className="task-list">
              {tasks.map((task) => (
                <article key={task.id} className="task-item">
                  <div className="task-header">
                    <strong>{task.title}</strong>
                    <span className="pill">{task.priority}</span>
                  </div>
                  <p>{task.description}</p>
                  <div className="task-meta">
                    <span>Status: {task.status}</span>
                    <span>Owner: {task.assignee_name || 'Unassigned'}</span>
                    <span>Due: {task.due_date || 'TBD'}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'new-task' && (
          <section className="panel">
            <h3>Create a new task</h3>
            <form className="task-form" onSubmit={handleCreateTask}>
              <label>
                Title
                <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Example: Replace printer cartridge" required />
              </label>
              <label>
                Description
                <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows="4" placeholder="Describe the request, issue, or action needed." required />
              </label>
              <div className="form-row">
                <label>
                  Priority
                  <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </label>
                <label>
                  Due date
                  <input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} />
                </label>
              </div>
              <label>
                Assignee ID
                <input value={form.assignee} onChange={(event) => setForm({ ...form, assignee: event.target.value })} placeholder="Leave empty for self-assignment" />
              </label>
              <button type="submit">Create task</button>
            </form>
          </section>
        )}

        {view === 'attendance' && token && (
          <section className="content-grid">
            <div className="panel wide-panel attendance-actions">
              <div>
                <h3>Today's attendance</h3>
                <p className="muted">A missing check-in is flagged for review; it is not automatically treated as an absence.</p>
              </div>
              <div className="button-row">
                <button onClick={() => handleAttendanceAction('check-in')}>Check in</button>
                <button className="secondary" onClick={() => handleAttendanceAction('check-out')}>Check out</button>
              </div>
              <p className="muted">
                {attendance.find((record) => record.work_date === localDate())
                  ? `Today's status: ${attendance.find((record) => record.work_date === localDate()).status}`
                  : 'No check-in recorded yet.'}
              </p>
            </div>

            <div className="panel wide-panel">
              <div className="section-heading">
                <h3>Attendance history</h3>
                {isManager && <button className="secondary" onClick={handleReport}>Daily team report</button>}
              </div>
              {attendance.length ? (
                <div className="task-list">
                  {attendance.map((record) => (
                    <article className="task-item" key={record.id}>
                      <div className="task-header">
                        <strong>{record.work_date} · {record.employee_name}</strong>
                        <span className="pill">{record.status}{record.is_remote ? ' · remote' : ''}</span>
                      </div>
                      <div className="task-meta">
                        <span>In: {record.check_in ? new Date(record.check_in).toLocaleTimeString() : 'Not recorded'}</span>
                        <span>Out: {record.check_out ? new Date(record.check_out).toLocaleTimeString() : 'Not recorded'}</span>
                        <span>Recorded duration: {record.worked_minutes === null ? 'Incomplete' : `${record.worked_minutes} minutes`}</span>
                      </div>
                      {isManager && (
                        <details className="correction-details">
                          <summary>Correct attendance (reason required)</summary>
                          <form className="task-form compact-form" onSubmit={(event) => handleAttendanceCorrection(event, record)}>
                            <div className="form-row">
                              <label>Check-in<input name="check_in" type="datetime-local" defaultValue={localDateTime(record.check_in)} /></label>
                              <label>Check-out<input name="check_out" type="datetime-local" defaultValue={localDateTime(record.check_out)} /></label>
                            </div>
                            <div className="form-row">
                              <label>Classification
                                <select name="status" defaultValue={record.status}>
                                  <option value="present">Present</option><option value="late">Late</option><option value="absent">Absent</option><option value="on_leave">On leave</option><option value="half_day">Half day</option><option value="pending_review">Pending review</option>
                                </select>
                              </label>
                              <label className="checkbox-label"><input type="checkbox" name="is_remote" defaultChecked={record.is_remote} /> Remote work</label>
                            </div>
                            <label>Correction reason<textarea name="correction_reason" rows="2" required /></label>
                            <button type="submit">Save correction</button>
                          </form>
                        </details>
                      )}
                    </article>
                  ))}
                </div>
              ) : <p className="muted">No attendance records yet.</p>}
              {attendanceReport && (
                <div className="report-box">
                  <strong>Missing check-ins requiring review</strong>
                  {attendanceReport.missing_check_ins.length ? attendanceReport.missing_check_ins.map((record) => (
                    <p key={`${record.employee}-${record.work_date}`}>{record.employee_name} · {record.work_date} · Pending review</p>
                  )) : <p className="muted">No missing check-ins for the selected day.</p>}
                  <strong>Missing check-outs requiring review</strong>
                  {attendanceReport.missing_check_outs.length ? attendanceReport.missing_check_outs.map((record) => (
                    <p key={`${record.employee}-${record.work_date}`}>{record.employee_name} · {record.work_date} · Missing check-out</p>
                  )) : <p className="muted">No missing check-outs for the selected day.</p>}
                </div>
              )}
            </div>

            <div className="panel wide-panel">
              <h3>Leave requests</h3>
              <form className="task-form compact-form" onSubmit={handleLeaveRequest}>
                <div className="form-row">
                  <label>Start date<input type="date" value={leaveForm.start_date} onChange={(event) => setLeaveForm({ ...leaveForm, start_date: event.target.value })} required /></label>
                  <label>End date<input type="date" value={leaveForm.end_date} onChange={(event) => setLeaveForm({ ...leaveForm, end_date: event.target.value })} required /></label>
                </div>
                <label>Leave type
                  <select value={leaveForm.leave_type} onChange={(event) => setLeaveForm({ ...leaveForm, leave_type: event.target.value })}>
                    <option value="annual">Annual</option><option value="sick">Sick</option><option value="personal">Personal</option><option value="other">Other</option>
                  </select>
                </label>
                <button type="submit">Submit leave request</button>
              </form>
              <div className="task-list leave-list">
                {leaveRequests.map((leave) => (
                  <article className="task-item" key={leave.id}>
                    <div className="task-header"><strong>{leave.employee_name}: {leave.start_date} to {leave.end_date}</strong><span className="pill">{leave.status}</span></div>
                    <p>{leave.leave_type}{leave.review_note ? ` · ${leave.review_note}` : ''}</p>
                    {isManager && leave.status === 'pending' && (
                      <div className="button-row">
                        <button onClick={() => handleLeaveReview(leave.id, 'approved')}>Approve</button>
                        <button className="secondary" onClick={() => handleLeaveReview(leave.id, 'rejected')}>Reject</button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </div>

            {isManager && (
              <div className="panel wide-panel">
                <h3>Configure a work schedule</h3>
                <form className="task-form compact-form" onSubmit={handleScheduleCreate}>
                  <label>Employee
                    <select value={scheduleForm.employee} onChange={(event) => setScheduleForm({ ...scheduleForm, employee: event.target.value })} required>
                      <option value="">Select a direct report</option>
                      {employees.filter((employee) => employee.id !== profile?.id).map((employee) => (
                        <option value={employee.id} key={employee.id}>{employee.first_name || employee.username} {employee.last_name}</option>
                      ))}
                    </select>
                  </label>
                  <div className="form-row">
                    <label>Weekday
                      <select value={scheduleForm.weekday} onChange={(event) => setScheduleForm({ ...scheduleForm, weekday: event.target.value })}>
                        {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day, index) => <option value={index} key={day}>{day}</option>)}
                      </select>
                    </label>
                    <label>Grace period (minutes)<input type="number" min="0" value={scheduleForm.grace_period_minutes} onChange={(event) => setScheduleForm({ ...scheduleForm, grace_period_minutes: event.target.value })} /></label>
                  </div>
                  <div className="form-row">
                    <label>Start time<input type="time" value={scheduleForm.start_time} onChange={(event) => setScheduleForm({ ...scheduleForm, start_time: event.target.value })} required /></label>
                    <label>End time<input type="time" value={scheduleForm.end_time} onChange={(event) => setScheduleForm({ ...scheduleForm, end_time: event.target.value })} required /></label>
                  </div>
                  <label>Effective from<input type="date" value={scheduleForm.effective_from} onChange={(event) => setScheduleForm({ ...scheduleForm, effective_from: event.target.value })} required /></label>
                  <button type="submit">Save schedule</button>
                </form>
              </div>
            )}
          </section>
        )}

        {view === 'feedback' && token && (
          <section className="content-grid">
            {isManager && (
              <div className="panel wide-panel">
                <h3>Publish private employee feedback</h3>
                <form className="task-form compact-form" onSubmit={handleFeedbackCreate}>
                  <label>Employee
                    <select value={feedbackForm.employee} onChange={(event) => setFeedbackForm({ ...feedbackForm, employee: event.target.value })} required>
                      <option value="">Select a direct report</option>
                      {employees.filter((employee) => employee.id !== profile?.id).map((employee) => (
                        <option value={employee.id} key={employee.id}>{employee.first_name || employee.username} {employee.last_name}</option>
                      ))}
                    </select>
                  </label>
                  <label>Category
                    <select value={feedbackForm.category} onChange={(event) => setFeedbackForm({ ...feedbackForm, category: event.target.value })}>
                      <option value="positive_recognition">Positive recognition</option><option value="technical_skills">Technical skills</option><option value="communication_teamwork">Communication and teamwork</option><option value="task_quality">Task quality</option><option value="time_management">Time management</option><option value="areas_for_improvement">Areas for improvement</option><option value="coaching_development">Coaching and development</option>
                    </select>
                  </label>
                  <label>Feedback date<input type="date" value={feedbackForm.feedback_date} onChange={(event) => setFeedbackForm({ ...feedbackForm, feedback_date: event.target.value })} required /></label>
                  <label>Specific, constructive feedback<textarea rows="4" value={feedbackForm.content} onChange={(event) => setFeedbackForm({ ...feedbackForm, content: event.target.value })} required /></label>
                  <button type="submit">Publish feedback</button>
                </form>
              </div>
            )}

            <div className="panel wide-panel">
              <h3>Feedback history</h3>
              {feedback.length ? (
                <div className="task-list">
                  {feedback.map((item) => (
                    <article className="task-item" key={item.id}>
                      <div className="task-header"><strong>{item.employee_name} · {item.category.replaceAll('_', ' ')}</strong><span className="pill">{item.acknowledged_at ? 'acknowledged' : 'awaiting acknowledgement'}</span></div>
                      <p>{item.content}</p>
                      <div className="task-meta"><span>From: {item.author_name}</span><span>Date: {item.feedback_date}</span>{item.task_title && <span>Task: {item.task_title}</span>}</div>
                      {item.employee === profile?.id && (
                        <div className="feedback-response">
                          {!item.acknowledged_at && <button className="secondary" onClick={() => handleFeedbackAcknowledgement(item.id)}>Acknowledge receipt</button>}
                          {item.employee_response && <p><strong>Your response:</strong> {item.employee_response}</p>}
                          <form className="task-form compact-form" onSubmit={(event) => handleFeedbackResponse(event, item.id)}>
                            <label>Optional response<textarea rows="2" value={responseDrafts[item.id] ?? item.employee_response ?? ''} onChange={(event) => setResponseDrafts({ ...responseDrafts, [item.id]: event.target.value })} /></label>
                            <button type="submit">Save response</button>
                          </form>
                        </div>
                      )}
                      {isManager && (
                        <form className="task-form compact-form action-form" onSubmit={(event) => handleCreateAction(event, item)}>
                          <strong>Create a follow-up action</strong>
                          <label>Action title<input name="title" required /></label>
                          <div className="form-row">
                            <label>Assigned to
                              <select name="assigned_to" defaultValue={item.employee}>
                                <option value={item.employee}>{item.employee_name}</option>
                                <option value={item.author}>{item.author_name}</option>
                              </select>
                            </label>
                            <label>Due date<input name="due_date" type="date" /></label>
                          </div>
                          <button type="submit">Add follow-up</button>
                        </form>
                      )}
                      {!!item.action_items?.length && (
                        <ul className="action-list">
                          {item.action_items.map((action) => (
                            <li key={action.id}>
                              <span>{action.title} · {action.due_date || 'No due date'}</span>
                              {action.assigned_to === profile?.id || isManager ? (
                                <select value={action.status} onChange={(event) => handleActionStatus(action.id, event.target.value)}>
                                  <option value="open">Open</option><option value="in_progress">In progress</option><option value="completed">Completed</option>
                                </select>
                              ) : <span className="pill">{action.status}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </article>
                  ))}
                </div>
              ) : <p className="muted">No feedback records are available to you.</p>}
            </div>
            {feedbackActions.length > 0 && (
              <div className="panel wide-panel">
                <h3>Follow-up actions assigned to you</h3>
                <div className="task-list">
                  {feedbackActions.filter((action) => action.assigned_to === profile?.id).map((action) => (
                    <article className="task-item" key={action.id}>
                      <div className="task-header"><strong>{action.title}</strong><span className="pill">{action.status}</span></div>
                      <p>Due: {action.due_date || 'No due date'}</p>
                    </article>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
