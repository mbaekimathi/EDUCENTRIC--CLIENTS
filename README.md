# Educentric CLIENTS — Parent & Student Portal

Django portal for parents and students. Reads the same MySQL database as
`ADMINISTRATION` without owning or migrating shared tables.

## Stack

- **Backend:** Django 6.1, django-environ, WhiteNoise, Gunicorn-ready WSGI
- **DB:** Shared MySQL (`my-school-system`) via XAMPP-compatible MariaDB backend + connection pooling
- **Cache / sessions:** Redis when `REDIS_URL` is set; otherwise local cache + DB sessions
- **Frontend:** Tailwind CSS 3 + Alpine.js 3 (responsive PC / tablet / mobile)

## Setup

```bash
pip install -r requirements.txt
copy .env.example .env   # already matches shared DB settings
python manage.py migrate --run-syncdb   # only creates missing Django session tables if needed
python manage.py runserver 8001
```

Open http://127.0.0.1:8001/ — pick Student or Parent, select a learner, enter the portal.

## Shared database safety

Portal models use `managed = False` and map to:

- `admissions_student`
- `admissions_parentguardian`
- `employees_schoolprofile`

This app never alters those tables. Schema changes stay in ADMINISTRATION.

Sessions use cookie name `edu_clients_sessionid` so they do not collide with the admin app’s session cookie.
