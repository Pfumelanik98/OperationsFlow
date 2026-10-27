# Management Operations flow

Management Operations flow is an internal IT team operations platform for task management, employee attendance, leave requests, private feedback and development follow-up.

## Modules

- **Tasks:** administrators assign work; employees view assigned tasks and submit completion reports; managers review reports.
- **Attendance:** self-service check-in/out, schedule-aware late classification, manager approvals, administrator corrections with an audit trail, leave review and daily/weekly/monthly reporting.
- **Feedback:** private administrator-published feedback, employee acknowledgement and response, and assigned development actions.
- **Operations dashboard:** authorised users see task, attendance and follow-up summaries. The figures provide operational context; they are not performance ratings.

## Run locally (Git Bash)

The requirements support Python 3.14 by using Django 5.2.8 or newer in the 5.2
series. If you already have an environment with Django 5.1.2 installed, update
it with `python -m pip install -r requirements.txt` before starting the server.

From the project root:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Use `python` after activating `.venv`, not the Windows `py` launcher, which may select a different interpreter. If `.venv` is already active but Django is missing, install the requirements with `python -m pip install -r requirements.txt`.

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Sign in with the Django account; the API is served at http://localhost:8000.

## Roles and manager teams

The user role is Administrator, IT Manager or IT Employee. Set an employee's direct manager on the user record in Django admin (`/admin/`). A Django superuser is treated as an administrator by the API regardless of the OperationsFlow role. Managers can approve attendance and task completion reports for their direct reports, review leave requests, and access operational reporting. They cannot assign tasks, correct attendance, manage schedules, or publish feedback. Administrators assign tasks and manage organization-wide configuration. Existing accounts have no manager assigned until configured.

At sign-in, choose Administrator, Manager, or Employee. The selected type must match the authenticated account; it does not grant a role or additional access. Employees land on `/employee-dashboard` (the former `/my-workspace` route also redirects there), a personal view containing only their assigned tasks, attendance and leave requests, private feedback and development actions, and notifications. Managers land on `/team-dashboard`; administrators land on `/administration`. The backend scopes employee task, attendance, leave, feedback, action, notification, and dashboard queries to the authenticated account. Employees cannot assign, edit, delete, or change task status. They submit one completion report per assigned task; a report can be resubmitted only after a manager requests changes. Employees can acknowledge/respond to their own feedback, update actions assigned to them, and mark only their own notifications read.

## API overview

Authentication: `POST /api/auth/login/` with `username` and `password`. Send the returned token as `Authorization: Token <token>`.

Tasks are under `/api/tasks/`; `GET /api/tasks/my-tasks/` always returns only tasks assigned to the authenticated user. Task creation, assignment, editing, deletion, and comments are administrator-only. Employees submit their single completion report through `/api/task-reports/`; managers can review reports for direct reports at `/api/task-reports/{id}/review/`, approving or requesting changes.

Attendance endpoints are under `/api/v1/attendance/`:

- `POST check-in/` and `POST check-out/`
- `GET` and `GET me/` for authorised records
- `POST {id}/approve/` for a manager to approve a direct report's attendance
- `PATCH {id}/` to correct a record (administrator-only); a non-empty `correction_reason` is required and the old values are retained in audit history
- `GET reports/?period=daily|weekly|monthly&date=YYYY-MM-DD`
- `GET/POST leave-requests/` and `POST leave-requests/{id}/review/`
- `GET/POST schedules/` for schedule records (schedule changes are administrator-only)
- `GET/POST holidays/` for public holiday configuration (writes require an administrator)

Feedback endpoints are under `/api/v1/feedback/`:

- `GET` and `GET me/` for feedback visible to the caller
- `POST` to publish feedback (administrator-only)
- `POST {id}/acknowledge/` and `POST {id}/responses/` for the recipient
- `POST {id}/actions/` to create follow-up actions (administrator-only)
- `GET actions/` and `PATCH actions/{id}/` to view and update action status

The combined dashboard is `GET /api/v1/dashboard/employee-operations/`. The current user's role and manager are available at `GET /api/v1/accounts/me/`.

## Attendance rules and limitations

- The configured Django `TIME_ZONE` determines local work dates and schedule comparisons. For a South African deployment, configure `TIME_ZONE=Africa/Johannesburg`.
- Schedule-aware lateness uses a weekday schedule, its effective dates and grace period. A missing schedule does not imply that someone is late.
- A missing check-in is reported as `pending_review`; it is never automatically classified as absence. Managers approve submitted attendance; administrators alone can create manual records or make audited corrections.
- Approved leave and configured public holidays are excluded from expected-workday missing-check-in reports. Public holidays must be entered by an administrator; there is no external holiday calendar integration.
- `is_remote` is stored independently from attendance status, so remote work can also be late. A record is limited to one session per employee/day. Split shifts, overnight schedules, breaks and break-adjusted paid duration are not implemented; `worked_minutes` is gross elapsed time between check-in and check-out.

## Notifications and privacy

Feedback publication and leave decisions create in-app notifications. Run `python manage.py send_operations_reminders` periodically (for example, with Windows Task Scheduler) to notify action owners about due/overdue follow-ups and to flag missing scheduled check-ins for employees and their managers. The command is idempotent for each notification on a given day. Email delivery is not configured.

Use synthetic employee data in development and demos. Before any real workplace use, establish retention and correction policies, configure production secrets and hosts, disable debug mode, and review applicable employment and POPIA obligations. The included SQLite configuration and development defaults are not a production deployment configuration.

## Tests

```bash
python manage.py test tasks attendance feedback
```
