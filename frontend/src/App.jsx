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

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('opsflow-token') || '');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tasks, setTasks] = useState(mockTasks);
  const [view, setView] = useState('dashboard');
  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assignee: '',
  });
  const [message, setMessage] = useState('');

  const fetchTasks = async () => {
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/tasks/`, {
        headers: {
          Authorization: `Token ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('API unavailable');

      const data = await response.json();
      setTasks(data);
    } catch (error) {
      setTasks(mockTasks);
      setMessage('Showing local demo data because the backend is not running yet.');
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
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const payload = await response.json();
      setToken(payload.token);
      localStorage.setItem('opsflow-token', payload.token);
      setMessage('Signed in successfully.');
    } catch (error) {
      setMessage('Login failed. Use a valid Django user or keep the demo mode.');
    }
  };

  const handleCreateTask = async (event) => {
    event.preventDefault();
    if (!token) {
      setMessage('Please sign in before creating a task.');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/tasks/`, {
        method: 'POST',
        headers: {
          Authorization: `Token ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...form,
          requester: 1,
        }),
      });

      if (!response.ok) throw new Error('Task creation failed');
      setForm({ title: '', description: '', priority: 'medium', due_date: '', assignee: '' });
      setView('dashboard');
      setMessage('Task created successfully.');
      fetchTasks();
    } catch (error) {
      setMessage('The task could not be created. Check your permissions or backend connection.');
    }
  };

  const pendingCount = tasks.filter((task) => task.status !== 'completed').length;
  const overdueCount = tasks.filter((task) => task.status !== 'completed' && task.due_date && task.due_date < new Date().toISOString().slice(0, 10)).length;
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
            <button className="logout" onClick={() => { localStorage.removeItem('opsflow-token'); setToken(''); setMessage('Signed out.'); }}>
              Sign out
            </button>
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
      </main>
    </div>
  );
}

export default App;
