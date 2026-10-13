# OperationsFlow

OperationsFlow is an internal IT team operations platform for task management, employee attendance, leave requests, private feedback and development follow-up.

## Modules

- **Tasks:** assign work, track deadlines, status, comments and task history.
- **Attendance:** self-service check-in/out, schedule-aware late classification, manager corrections with an audit trail, leave review and daily/weekly/monthly reporting.
- **Feedback:** private manager feedback, employee acknowledgement and response, and assigned development actions.
- **Operations dashboard:** authorised users see task, attendance and follow-up summaries. The figures provide operational context; they are not performance ratings.

## Run locally (Git Bash)

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

The user role is Administrator, IT Manager or IT Employee. Set an employee's direct manager on the user record in Django admin (`/admin/`). Attendance and feedback access for managers is limited to their direct reports; administrators can manage all users. Existing accounts have no manager assigned until configured.

## API overview

Authentication: `POST /api/auth/login/` with `username` and `password`. Send the returned token as `Authorization: Token <token>`.

Attendance endpoints are under `/api/v1/attendance/`:

- `POST check-in/` and `POST check-out/`
- `GET` and `GET me/` for authorised records
- `PATCH {id}/` to correct a record; a non-empty `correction_reason` is required and the old values are retained in audit history
- `GET reports/?period=daily|weekly|monthly&date=YYYY-MM-DD`
- `GET/POST leave-requests/` and `POST leave-requests/{id}/review/`
- `GET/POST schedules/` for schedule records the caller is authorised to manage
- `GET/POST holidays/` for public holiday configuration (writes require an administrator)

Feedback endpoints are under `/api/v1/feedback/`:

- `GET` and `GET me/` for feedback visible to the caller
- `POST` to publish manager feedback
- `POST {id}/acknowledge/` and `POST {id}/responses/` for the recipient
- `POST {id}/actions/` to create follow-up actions
- `GET actions/` and `PATCH actions/{id}/` to view and update action status

The combined dashboard is `GET /api/v1/dashboard/employee-operations/`. The current user's role and manager are available at `GET /api/v1/accounts/me/`.

## Attendance rules and limitations

- The configured Django `TIME_ZONE` determines local work dates and schedule comparisons. For a South African deployment, configure `TIME_ZONE=Africa/Johannesburg`.
- Schedule-aware lateness uses a weekday schedule, its effective dates and grace period. A missing schedule does not imply that someone is late.
- A missing check-in is reported as `pending_review`; it is never automatically classified as absence. A manager must explicitly record or correct attendance with a reason.
- Approved leave and configured public holidays are excluded from expected-workday missing-check-in reports. Public holidays must be entered by an administrator; there is no external holiday calendar integration.
- `is_remote` is stored independently from attendance status, so remote work can also be late. A record is limited to one session per employee/day. Split shifts, overnight schedules, breaks and break-adjusted paid duration are not implemented; `worked_minutes` is gross elapsed time between check-in and check-out.

## Notifications and privacy

Feedback publication and leave decisions create in-app notifications. Run `python manage.py send_operations_reminders` periodically (for example, with Windows Task Scheduler) to notify action owners about due/overdue follow-ups and to flag missing scheduled check-ins for employees and their managers. The command is idempotent for each notification on a given day. Email delivery is not configured.

Use synthetic employee data in development and demos. Before any real workplace use, establish retention and correction policies, configure production secrets and hosts, disable debug mode, and review applicable employment and POPIA obligations. The included SQLite configuration and development defaults are not a production deployment configuration.

## Tests

```bash
python manage.py test tasks attendance feedback
```
