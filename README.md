# CampusSwap

CampusSwap is a Flask marketplace for campus listings. Vercel detects the
Flask application in `app.py` and installs its runtime dependency from
`requirements.txt`; no custom build command or output directory is needed.

## Deploy to Vercel

1. Import this GitHub repository in Vercel. If the app is inside a larger
   repository, set **Root Directory** to `olxforbooks`.
2. Leave the framework preset, build command, and output directory at their
   detected/default values.
3. Add a `SECRET_KEY` environment variable for Preview and Production. Generate
   one locally with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. Deploy. Vercel will serve the Flask routes, including `/listings/new` and
   `/listings/<id>`.

For local development:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python app.py
```

## Database note

The app uses SQLite. Locally it stores data in `instance/campusswap.sqlite3`;
on Vercel it uses `/tmp/campusswap.sqlite3`, because the deployed project
filesystem is not writable. Vercel's `/tmp` storage is temporary and isolated
per Function instance, so listings can disappear after an instance is recycled
and may not be shared between instances. This setup is suitable for trying the
deployment, but not for a live marketplace. Before relying on persistent
listings, migrate the SQLite data layer to a managed database such as Neon or
Supabase Postgres. `DATABASE_PATH` can override the SQLite file location where
a persistent writable filesystem is available; it does not make Vercel's
filesystem persistent.
