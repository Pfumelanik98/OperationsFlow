import { useEffect, useState } from 'react';

const API_BASE_URL = 'http://localhost:8000/api';
const API_V1_URL = `${API_BASE_URL}/v1`;
const pathViews = {
  '/employee-dashboard': 'workspace',
  '/my-workspace': 'workspace',
  '/team-dashboard': 'dashboard',
  '/administration': 'dashboard',
  '/tasks': 'tasks',
  '/new-task': 'new-task',
  '/attendance': 'attendance',
  '/feedback': 'feedback',
  '/task-reports': 'task-reports',
};
const pathsForViews = {
  workspace: '/employee-dashboard',
  dashboard: '/team-dashboard',
  tasks: '/tasks',
  'new-task': '/new-task',
  attendance: '/attendance',
  feedback: '/feedback',
  'task-reports': '/task-reports',
};
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
  const [loginRole, setLoginRole] = useState('');
  const [tasks, setTasks] = useState([]);
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(Boolean(token));
  const [attendance, setAttendance] = useState([]);
  const [attendanceReport, setAttendanceReport] = useState(null);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [feedbackActions, setFeedbackActions] = useState([]);
  const [taskReports, setTaskReports] = useState([]);
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
  const [view, setView] = useState(() => pathViews[window.location.pathname] || 'dashboard');
  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assignee: '',
  });
  const [message, setMessage] = useState('');

  const refreshData = async (authToken) => {
    const userData = await apiRequest(`${API_V1_URL}/accounts/me/`, authToken);
    const isEmployeeAccount = userData.role === 'it_employee' && !userData.is_superuser;
    const [taskData, attendanceData, leaveData, feedbackData, actionData, reportData, dashboardData, notificationData] = await Promise.all([
      apiRequest(`${API_BASE_URL}/tasks/${isEmployeeAccount ? 'my-tasks/' : ''}`, authToken),
      apiRequest(`${API_V1_URL}/attendance/`, authToken),
      apiRequest(`${API_V1_URL}/attendance/leave-requests/`, authToken),
      apiRequest(`${API_V1_URL}/feedback/`, authToken),
      apiRequest(`${API_V1_URL}/feedback/actions/`, authToken),
      apiRequest(`${API_BASE_URL}/task-reports/`, authToken),
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
    setTaskReports(reportData);
    setEmployees(userList);
    setOperationSummary(dashboardData.employees);
    setNotifications(notificationData);
    return userData;
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
      setTasks([]);
      setProfile(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    refreshData(token)
      .catch((error) => {
        if (!cancelled) setMessage(error.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const isAdministrator = Boolean(profile?.is_superuser || profile?.role === 'administrator');
  const isEmployee = profile?.role === 'it_employee' && !isAdministrator;
  const isManager = isAdministrator || profile?.role === 'it_manager';

  const navigate = (nextView) => {
    const safeView = isEmployee ? 'workspace' : nextView;
    const route = safeView === 'dashboard' && isAdministrator
      ? '/administration'
      : pathsForViews[safeView] || '/';
    window.history.pushState({}, '', route);
    setView(safeView);
  };

  useEffect(() => {
    if (token && profile) {
      const homeView = isEmployee ? 'workspace' : 'dashboard';
      const homePath = homeView === 'dashboard' && isAdministrator
        ? '/administration'
        : pathsForViews[homeView];
      window.history.replaceState({}, '', homePath);
      setView(homeView);
    } else if (!token) {
      window.history.replaceState({}, '', '/');
      setView('dashboard');
    }
  }, [token, profile?.id, profile?.role, profile?.is_superuser]);

  useEffect(() => {
    const handlePopState = () => {
      const requestedView = pathViews[window.location.pathname] || 'dashboard';
      if (isEmployee && requestedView !== 'workspace') {
        window.history.replaceState({}, '', '/my-workspace');
        setView('workspace');
        return;
      }
      if (
        profile?.role === 'it_manager'
        && !profile.is_superuser
        && window.location.pathname === '/administration'
      ) {
        window.history.replaceState({}, '', '/team-dashboard');
        setView('dashboard');
        return;
      }
      if (
        profile?.role === 'it_manager'
        && !profile.is_superuser
        && !['dashboard', 'attendance', 'task-reports'].includes(requestedView)
      ) {
        window.history.replaceState({}, '', '/team-dashboard');
        setView('dashboard');
        return;
      }
      setView(requestedView);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [isEmployee, profile?.role, profile?.is_superuser]);

  const handleLogin = async (event) => {
    event.preventDefault();
    try {
      const payload = await apiRequest(`${API_BASE_URL}/auth/login/`, '', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      const userData = await apiRequest(`${API_V1_URL}/accounts/me/`, payload.token);
      const actualRole = userData.is_superuser || userData.role === 'administrator'
        ? 'administrator'
        : userData.role;
      if (actualRole !== loginRole) {
        throw new Error('The selected account type does not match your user account.');
      }
      setProfile(null);
      setIsLoading(true);
      setToken(payload.token);
      localStorage.setItem('opsflow-token', payload.token);
      setMessage(`Signed in successfully as ${loginRole === 'it_employee' ? 'Employee' : loginRole === 'it_manager' ? 'Manager' : 'Administrator'}.`);
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
      navigate('dashboard');
      setMessage('Task created successfully.');
      fetchTasks();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleCompletionReport = async (event, task) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const existingReport = taskReports.find((report) => report.task === task.id);
    const body = {
      summary: data.get('summary'),
      issues: data.get('issues'),
      time_spent_minutes: data.get('time_spent_minutes') || null,
    };
    try {
      if (existingReport?.status === 'changes_requested') {
        await apiRequest(`${API_BASE_URL}/task-reports/${existingReport.id}/`, token, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        setMessage('Completion report resubmitted for review.');
      } else {
        await apiRequest(`${API_BASE_URL}/task-reports/`, token, {
          method: 'POST',
          body: JSON.stringify({ task: task.id, ...body }),
        });
        setMessage('Completion report submitted for manager approval.');
      }
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleTaskReportReview = async (event, report, status) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget.form);
    const reviewNote = data.get('review_note') || '';
    if (status === 'changes_requested' && !reviewNote.trim()) {
      setMessage('Add a note explaining the requested changes.');
      return;
    }
    try {
      await apiRequest(`${API_BASE_URL}/task-reports/${report.id}/review/`, token, {
        method: 'POST',
        body: JSON.stringify({ status, review_note: reviewNote }),
      });
      setMessage(status === 'approved' ? 'Task report approved.' : 'Changes requested from employee.');
      await refreshData(token);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const handleAttendanceApproval = async (record) => {
    try {
      await apiRequest(`${API_V1_URL}/attendance/${record.id}/approve/`, token, {
        method: 'POST',
      });
      setMessage('Employee attendance approved.');
      await refreshData(token);
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

  const pendingCount = tasks.filter((task) => task.status !== 'completed').length;
  const overdueCount = tasks.filter((task) => task.status !== 'completed' && task.due_date && task.due_date < localDate()).length;
  const lowPriorityCount = tasks.filter((task) => task.priority === 'low').length;
  const todayAttendance = attendance.find((record) => record.work_date === localDate());

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">OF</div>
          <div>
            <h1>Management Operations flow</h1>
            <p>Internal IT workflow</p>
          </div>
        </div>

        <nav className="nav">
          {token && profile && isEmployee ? (
            <button className={view === 'workspace' ? 'active' : ''} onClick={() => navigate('workspace')}>
              Employee dashboard
            </button>
          ) : token && profile ? (
            <>
              <button className={view === 'dashboard' ? 'active' : ''} onClick={() => navigate('dashboard')}>
                {isAdministrator ? 'Administration' : 'Team dashboard'}
              </button>
              {isManager && (
                <button className={view === 'task-reports' ? 'active' : ''} onClick={() => navigate('task-reports')}>
                  Task reports
                </button>
              )}
              {isAdministrator && (
                <>
                  <button className={view === 'tasks' ? 'active' : ''} onClick={() => navigate('tasks')}>
                    Active tasks
                  </button>
                  <button className={view === 'new-task' ? 'active' : ''} onClick={() => navigate('new-task')}>
                    Assign task
                  </button>
                  <button className={view === 'feedback' ? 'active' : ''} onClick={() => navigate('feedback')}>
                    Feedback & development
                  </button>
                </>
              )}
              <button className={view === 'attendance' ? 'active' : ''} onClick={() => navigate('attendance')}>
                {isManager ? 'Attendance approvals' : 'Attendance & leave'}
              </button>
            </>
          ) : null}
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Operations</p>
            <h2>{isEmployee ? 'Employee dashboard' : isAdministrator ? 'Administration' : 'Team dashboard'}</h2>
          </div>
          {!token ? (
            <form className="login-form" onSubmit={handleLogin}>
              <select aria-label="Sign in as" value={loginRole} onChange={(event) => setLoginRole(event.target.value)} required>
                <option value="" disabled>Choose account type</option>
                <option value="administrator">Administrator</option>
                <option value="it_manager">Manager</option>
                <option value="it_employee">Employee</option>
              </select>
              <input aria-label="Username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" required />
              <input aria-label="Password" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" required />
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
          {token && profile && !isEmployee && (
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

        {token && isLoading && <div className="panel" role="status">Loading your private workspace…</div>}
        {!token && (
          <section className="panel">
            <h3>Sign in to Management Operations flow</h3>
            <p className="muted">Choose your account type. Your own role determines which dashboard and information you can access.</p>
          </section>
        )}

        {view === 'workspace' && token && profile && isEmployee && !isLoading && (
          <section className="workspace-grid">
            <div className="panel workspace-welcome">
              <p className="eyebrow">Employee dashboard</p>
              <h3>Welcome, {profile.first_name || profile.username}</h3>
              <p className="muted">Your tasks, attendance, feedback and notifications in one place.</p>
            </div>

            <section className="panel workspace-section">
              <div className="section-heading">
                <div>
                  <h3>My Tasks</h3>
                  <p className="muted">{pendingCount} active · {overdueCount} overdue</p>
                </div>
              </div>
              {tasks.length ? (
                <div className="task-list">
                  {tasks.map((task) => {
                    const overdue = task.status !== 'completed' && task.due_date && task.due_date < localDate();
                    const completionReport = taskReports.find((report) => report.task === task.id);
                    return (
                      <article className="task-item" key={task.id}>
                        <div className="task-header">
                          <strong>{task.title}</strong>
                          <span className="pill">{task.priority}</span>
                        </div>
                        <p>{task.description}</p>
                        <div className="task-meta">
                          <span>Due: {task.due_date || 'No deadline'}{overdue ? ' · Overdue' : ''}</span>
                          <span>Assigned by: {task.requester_name || 'Operations'}</span>
                        </div>
                        <p className="muted">Status: {task.status.replaceAll('_', ' ')}</p>
                        {completionReport && completionReport.status !== 'changes_requested' ? (
                          <div className="report-box">
                            <strong>Completion report: {completionReport.status.replaceAll('_', ' ')}</strong>
                            <p>{completionReport.summary}</p>
                            {completionReport.issues && <p>Issues: {completionReport.issues}</p>}
                            {completionReport.review_note && <p>Manager note: {completionReport.review_note}</p>}
                          </div>
                        ) : task.status !== 'completed' ? (
                          <form className="task-form compact-form" onSubmit={(event) => handleCompletionReport(event, task)}>
                            <strong>{completionReport ? 'Update report requested by your manager' : 'Submit completion report'}</strong>
                            {completionReport?.review_note && <p className="muted">Manager note: {completionReport.review_note}</p>}
                            <label>Work completed
                              <textarea name="summary" rows="3" defaultValue={completionReport?.summary || ''} required />
                            </label>
                            <label>Issues or blockers (optional)
                              <textarea name="issues" rows="2" defaultValue={completionReport?.issues || ''} />
                            </label>
                            <label>Time spent (minutes, optional)
                              <input
                                name="time_spent_minutes"
                                type="number"
                                min="0"
                                defaultValue={completionReport?.time_spent_minutes ?? ''}
                              />
                            </label>
                            <button type="submit">{completionReport ? 'Resubmit report' : 'Submit for approval'}</button>
                          </form>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              ) : <p className="muted">You have no assigned tasks.</p>}
            </section>

            <section className="panel workspace-section">
              <h3>My Attendance</h3>
              <div className="button-row">
                <button onClick={() => handleAttendanceAction('check-in')}>Check in</button>
                <button className="secondary" onClick={() => handleAttendanceAction('check-out')}>Check out</button>
              </div>
              {todayAttendance ? (
                <p>
                  Today: {todayAttendance.status}
                  {' · In: '}{todayAttendance.check_in
                    ? new Date(todayAttendance.check_in).toLocaleTimeString()
                    : 'Not recorded'}
                  {' · Out: '}{todayAttendance.check_out
                    ? new Date(todayAttendance.check_out).toLocaleTimeString()
                    : 'Not recorded'}
                </p>
              ) : <p className="muted">No attendance recorded today.</p>}
              <h4>Recent history</h4>
              {attendance.length ? (
                <ul className="workspace-list">
                  {attendance.slice(0, 5).map((record) => (
                    <li key={record.id}>
                      <span>{record.work_date}</span>
                      <span className="pill">{record.status}</span>
                      <span>{record.check_in ? new Date(record.check_in).toLocaleTimeString() : 'No check-in'}</span>
                      <span>{record.check_out ? new Date(record.check_out).toLocaleTimeString() : 'No check-out'}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="muted">No attendance history yet.</p>}
            </section>

            <section className="panel workspace-section">
              <h3>My Leave</h3>
              <p className="muted">Request time off and track the decision separately from your attendance.</p>
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
              <h4>My leave requests</h4>
              {leaveRequests.length ? leaveRequests.map((leave) => (
                <p key={leave.id}>{leave.start_date} to {leave.end_date} · {leave.leave_type} · {leave.status}</p>
              )) : <p className="muted">No leave requests.</p>}
            </section>

            <section className="panel workspace-section">
              <h3>My Feedback</h3>
              {feedback.filter((item) => item.employee === profile.id).length ? (
                <div className="task-list">
                  {feedback.filter((item) => item.employee === profile.id).map((item) => (
                    <article className="task-item" key={item.id}>
                      <div className="task-header">
                        <strong>{item.category.replaceAll('_', ' ')}</strong>
                        <span className="pill">{item.acknowledged_at ? 'acknowledged' : 'awaiting acknowledgement'}</span>
                      </div>
                      <p>{item.content}</p>
                      <div className="task-meta"><span>From: {item.author_name}</span><span>Date: {item.feedback_date}</span></div>
                      {!item.acknowledged_at && <button className="secondary" onClick={() => handleFeedbackAcknowledgement(item.id)}>Acknowledge</button>}
                      {item.employee_response && <p><strong>Your response:</strong> {item.employee_response}</p>}
                      <form className="task-form compact-form" onSubmit={(event) => handleFeedbackResponse(event, item.id)}>
                        <label>Response
                          <textarea
                            rows="2"
                            value={responseDrafts[item.id] ?? item.employee_response ?? ''}
                            onChange={(event) => setResponseDrafts({ ...responseDrafts, [item.id]: event.target.value })}
                          />
                        </label>
                        <button type="submit">Save response</button>
                      </form>
                    </article>
                  ))}
                </div>
              ) : <p className="muted">No feedback is available for you.</p>}
              {feedbackActions.some((action) => action.assigned_to === profile.id) && (
                <div>
                  <h4>Development actions assigned to you</h4>
                  <ul className="action-list">
                    {feedbackActions.filter((action) => action.assigned_to === profile.id).map((action) => (
                      <li key={action.id}>
                        <span>{action.title} · {action.due_date || 'No due date'}</span>
                        <select value={action.status} onChange={(event) => handleActionStatus(action.id, event.target.value)}>
                          <option value="open">Open</option>
                          <option value="in_progress">In progress</option>
                          <option value="completed">Completed</option>
                        </select>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section className="panel workspace-section">
              <h3>My Notifications</h3>
              {notifications.length ? notifications.map((notification) => (
                <div className={`notification-row ${notification.is_read ? 'read' : ''}`} key={notification.id}>
                  <span>{notification.message}</span>
                  {!notification.is_read && <button className="secondary" onClick={() => handleMarkNotificationRead(notification.id)}>Mark read</button>}
                </div>
              )) : <p className="muted">No notifications yet.</p>}
            </section>
          </section>
        )}

        {view === 'dashboard' && token && profile && !isEmployee && !isLoading && (
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

        {view === 'task-reports' && token && profile && !isEmployee && (
          <section className="panel">
            <h3>Employee task completion reports</h3>
            {taskReports.length ? (
              <div className="task-list">
                {taskReports.map((report) => (
                  <article className="task-item" key={report.id}>
                    <div className="task-header">
                      <strong>{report.task_title}</strong>
                      <span className="pill">{report.status.replaceAll('_', ' ')}</span>
                    </div>
                    <p><strong>Employee:</strong> {report.employee_name}</p>
                    <p>{report.summary}</p>
                    {report.issues && <p><strong>Issues:</strong> {report.issues}</p>}
                    {report.time_spent_minutes !== null && (
                      <p><strong>Time spent:</strong> {report.time_spent_minutes} minutes</p>
                    )}
                    {report.review_note && <p><strong>Previous review note:</strong> {report.review_note}</p>}
                    {report.status === 'submitted' && (
                      <form className="task-form compact-form" onSubmit={(event) => event.preventDefault()}>
                        <label>Review note
                          <textarea name="review_note" rows="2" required={false} />
                        </label>
                        <div className="button-row">
                          <button type="button" onClick={(event) => handleTaskReportReview(event, report, 'approved')}>Approve report</button>
                          <button type="button" className="secondary" onClick={(event) => handleTaskReportReview(event, report, 'changes_requested')}>Request changes</button>
                        </div>
                      </form>
                    )}
                    {report.reviewed_by_name && (
                      <p className="muted">Reviewed by {report.reviewed_by_name}{report.reviewed_at ? ` · ${new Date(report.reviewed_at).toLocaleString()}` : ''}</p>
                    )}
                  </article>
                ))}
              </div>
            ) : <p className="muted">No completion reports have been submitted.</p>}
          </section>
        )}

        {view === 'tasks' && (
          token && profile && isAdministrator &&
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
          token && profile && isAdministrator &&
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
                Employee
                <select value={form.assignee} onChange={(event) => setForm({ ...form, assignee: event.target.value })} required>
                  <option value="">Select employee</option>
                  {employees.filter((employee) => employee.role === 'it_employee').map((employee) => (
                    <option value={employee.id} key={employee.id}>
                      {[employee.first_name, employee.last_name].filter(Boolean).join(' ') || employee.username}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit">Create task</button>
            </form>
          </section>
        )}

        {view === 'attendance' && token && profile && !isEmployee && (
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
                        <span>{record.approved_at ? `Approved by ${record.approved_by_name || 'manager'} · ${new Date(record.approved_at).toLocaleString()}` : 'Awaiting manager approval'}</span>
                      </div>
                      {isManager && !record.approved_at && (isAdministrator || record.employee !== profile?.id) && (
                        <button className="secondary" onClick={() => handleAttendanceApproval(record)}>Approve attendance</button>
                      )}
                      {isAdministrator && (
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

            {isAdministrator && (
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

        {view === 'feedback' && token && profile && isAdministrator && (
          <section className="content-grid">
            {isAdministrator && (
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
                      {isAdministrator && (
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
                              {action.assigned_to === profile?.id || isAdministrator ? (
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
