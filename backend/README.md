# UniFlow API

Local development (from the repository root):

```sh
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
```

Start with a real administrator and provision employees through the administration API. There is no demo authentication endpoint or automatic frontend login. The legacy seed command is retained only for old data fixtures; its accounts cannot authenticate. Browser tests use explicit password-based test accounts and an isolated database.

Tests:

```sh
cd backend
../.venv/bin/python manage.py test core --verbosity 2
```

The client first requests `GET /api/auth/session/` to obtain a CSRF cookie, then sends its `csrftoken` in the `X-CSRFToken` header for unsafe requests. Authentication is an HttpOnly session cookie. Development frontend traffic should proxy `/api` to this server; do not expose unauthenticated `/media` routes. Every attachment is downloaded through its authenticated API endpoint.

Profile organization and roles are read-only in the employee API. Reviewers see only submitted/returned/approved reports from their own department, cannot decide their own reports, and cannot edit authors' records. Administrators can inspect all departments' reports and activities and review other authors' submitted reports. Each submission requires at least one owned activity with a file or link. Submitted/approved reports and their linked activities are immutable. Returning requires a meaningful comment and allows author correction/resubmission. Objects expose read-only `owner_id`; client ownership checks should use it rather than a display name.

## Administration

`python manage.py createsuperuser` provisions the first real administrator. Both Django staff/superuser flags and the `administrator` profile role map to institutional administration capabilities. Legacy demo identities are not login accounts. Session responses include `is_demo` and `capabilities`; demo account passwords cannot be changed.

Administrator-only endpoints:

* `GET/POST /api/admin/users/` and `PATCH /api/admin/users/{id}/`: provision real username/password accounts, edit their organization and role, or deactivate them. Passwords are write-only, validated and hashed. Accounts cannot be deleted through this API. Last active administrator protection prevents losing administration access.
* `GET/POST /api/admin/departments/` and `PATCH /api/admin/departments/{id}/`: maintain `name`, `faculty`, `head_name`. Renames propagate to assigned profile department/faculty names. User assignment requires a known department; reviewers require one.
* `GET/POST /api/admin/templates/` and `PATCH /api/admin/templates/{slug}/`: maintain `title`, `description`, `type`, `version`, `fields`, `form_schema`, `icon`, `is_active`. List endpoints return plain arrays. Content changes require a new version; template IDs remain stable. Workspace only exposes active templates.

Templates have optional structured fields:

```json
{
  "form_schema": [
    {"key": "journal_name", "label": "Jurnal nomi", "type": "text", "required": true},
    {"key": "pages", "label": "Sahifalar", "type": "number", "required": false}
  ]
}
```

Up to 20 unique field keys matching `^[a-z][a-z0-9_]{0,49}$` are accepted. Field types: `text`, `textarea`, `number`, `date`, `url`. Labels have a maximum of 120 characters. New reports optionally select `template_id`; otherwise they use an active template for their type. If there is no active matching template, creation is rejected. Legacy drafts without a saved template/version must be recreated before submission; existing valid drafts keep their saved schema even after template deactivation. They store a read-only `template_version` and `template_snapshot`, including the exact schema, so future template edits cannot change an existing report's requirements. Answers go in writable `extra_data`, e.g. `{"journal_name": "Journal", "pages": 12}`. Drafts may be incomplete; submission enforces required fields, numeric JSON numbers, ISO dates, HTTP(S) URLs, and rejects keys outside the report's saved schema.

`POST /api/auth/password/` accepts `current_password` and `new_password`. It validates both, rejects reuse, preserves the current session and invalidates previous password-based session hashes. Login attempts are limited per hashed username/IP pair and by a separate broad IP ceiling. Development uses a process-local cache. Production requires `DJANGO_REDIS_URL` and uses shared Redis counters across workers; Compose supplies an internal Redis service. A separate PostgreSQL/Redis CI job verifies workflow SQL and cache sharing across independent Python processes. The broad IP limit still needs the actual deployment’s trusted client-IP configuration (see `docs/REMAINING_WORK.md`).

For deployment, set `DJANGO_DEBUG=0`, supply a unique `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, use HTTPS and a production WSGI server. The demo authentication endpoint has been removed; test fixture creation is disabled outside DEBUG. SQLite and local files are development defaults; production needs a managed database, protected durable file storage, backups, a shared rate-limit cache, and your actual institutional approval rules. This version implements one reviewer decision per report, not multi-level legal signing or payroll.
