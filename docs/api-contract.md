# UniFlow development API contract

All endpoints below use `/api/`. JSON and multipart uploads are supported. Session authentication with CSRF protection. Authentication always requires a real username/password; there is no demo login endpoint. Role values: `employee`, `reviewer`, `administrator`.

* `GET auth/session/` -> `{ user }` or 401; sets CSRF cookie.
* `POST auth/demo/` -> 404 (removed).
* `POST auth/login/` body `{username,password}` -> `{user}`.
* `POST auth/logout/` -> 204.
* `POST auth/password/` body `{current_password,new_password}` -> 204. Validates password and preserves the current session.
* `GET workspace/` -> `{user, profile, activities, reports, work_items, notifications, templates}`. Employees only see their records; reviewers see reviewable records.
* `GET/PATCH profile/` -> Profile.
* `POST activities/`, `PATCH/DELETE activities/:id/`.
* `POST reports/`, `PATCH reports/:id/` for own drafts/returned reports. DELETE only removes never-submitted drafts; submitted history is retained.
* `POST reports/:id/submit/` validates fields/evidence and atomically stores an immutable numbered submission snapshot and attachment references. The review department is fixed at first submission.
* `POST reports/:id/review/` body `{decision:'approved'|'returned',comment}`; reviewer only, comment required on return. Author cannot review own report.
* `POST attachments/` multipart `{file}` -> Attachment. Authenticated file download at returned URL.
* `POST work-items/`, `PATCH/DELETE work-items/:id/`.
* `POST notifications/:id/read/` -> notification.
* `GET/POST admin/users/`, `PATCH admin/users/:id/` -> administrator-only real account management; password is write-only, deactivation preserves records.
* `GET/POST admin/departments/`, `PATCH admin/departments/:id/` -> `{id,name,faculty,head_name}`.
* `GET admin/audit/` -> paginated read-only administration events (administrator only); password values/hashes are excluded.
* `GET/POST admin/templates/`, `PATCH admin/templates/:id/` -> versioned templates. Content changes require a new version. `fields` are descriptive sections; `form_schema` defines actual custom inputs.

Objects (all IDs numeric):

```
User: {id, name, email, role, initials, is_demo, capabilities}
Profile: {id, full_name, email, phone, department, faculty, position, degree, bio, employee_id, initials, experience_years, employment_type}
Attachment: {id, name, url, size}
Activity: {id, title, category, date, description, link, status, attachment: Attachment|null, created_at, owner_name, owner_id}
  category: article|conference|certificate|teaching|project
  status: draft|verified (server-controlled; creating/editing yields draft)
Report: {id,title,type,period,status,activity_ids:number[],comment,due_date,submitted_at,created_at,updated_at,owner_name,owner_id,history:History[],template_version,template_snapshot,review_department,submissions:Submission[],extra_data:{[key]:string|number}}
  type: scientific|annual|teaching|qualification
  status: draft|submitted|returned|approved
History: {id,action,actor_name,comment,created_at}
WorkItem: {id,title,category,target,completed,due_date}
Notification: {id,title,message,read,created_at,report_id:number|null}
Template: {id:string,title,description,type,version,fields:string[],icon:string,is_active,form_schema:FormField[]}
FormField: {key:string,label:string,type:text|textarea|number|date|url,required:boolean}
```

New reports accept optional `template_id` and snapshot the template version/schema. If omitted, the server selects an active matching template; if none exists, it returns a `template_id` validation error. Submission rejects legacy reports without a saved template/version. The client sends the selected ID explicitly. Existing reports cannot change type/template. `extra_data` can be incomplete in drafts; submission validates required fields and types against the saved snapshot. Submitted/approved reports cannot be edited. `due_date:null` clears an optional deadline. Activities accept `attachment_id` on write and expose an authenticated nested `attachment` on read.

Demo seed should represent an Uzbek university employee with an explicitly illustrative TATU context, 8+ activities, reports in varied statuses, work items, notification, and four templates. User data must persist in SQLite for local development. Tests must cover owner isolation, CSRF/auth, return/resubmit/approve, immutable submitted reports/evidence, attachment access, and invalid transitions. Return structured DRF validation errors.

Submission: `{id,number,created_at,snapshot:{title,type,period,owner_name,department,template_version,template_snapshot,extra_data,activities}}`. Download authorization includes retained attachment references in submission snapshots. Sensitive API responses use `Cache-Control: private, no-store`. Login and API throttles only trust forwarded client addresses from explicitly configured proxy CIDRs.
