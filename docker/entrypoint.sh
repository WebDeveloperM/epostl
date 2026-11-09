#!/bin/sh
# Konteyner ishga tushganda: bazani kutish → migratsiya → statik fayllar → (ixtiyoriy) admin va demo → asosiy buyruq
set -e

if [ "${SKIP_BOOTSTRAP:-0}" != "1" ]; then
    echo "[entrypoint] PostgreSQL kutilmoqda..."
    python - <<'PY'
import os, sys, time
import psycopg
import environ

url = environ.Env.db_url_config(os.environ["DATABASE_URL"])
for attempt in range(60):
    try:
        psycopg.connect(host=url["HOST"], port=url["PORT"] or 5432, user=url["USER"],
                        password=url["PASSWORD"], dbname=url["NAME"], connect_timeout=3).close()
        print("[entrypoint] PostgreSQL tayyor")
        sys.exit(0)
    except Exception as exc:
        print(f"[entrypoint] kutilmoqda ({attempt + 1}/60): {exc.__class__.__name__}")
        time.sleep(2)
sys.exit("[entrypoint] PostgreSQL'ga ulanib bo‘lmadi")
PY

    python manage.py migrate --noinput
    python manage.py collectstatic --noinput --verbosity 0

    if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
        python manage.py createsuperuser --noinput \
            --username "$DJANGO_SUPERUSER_USERNAME" --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.uz}" \
            2>/dev/null && echo "[entrypoint] Administrator yaratildi: $DJANGO_SUPERUSER_USERNAME" \
            || echo "[entrypoint] Administrator allaqachon mavjud"
    fi

    if [ "${SEED_DEMO:-0}" = "1" ]; then
        python manage.py seed_demo --force
    fi
fi

exec "$@"
