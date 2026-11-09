# Refleksiv portfolio platformasi — production image (Django + gunicorn)
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Bog‘liqliklar alohida qatlamda — kod o‘zgarganda qayta o‘rnatilmaydi
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' docker/*.sh \
    && chmod +x docker/*.sh \
    && groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /app app \
    && mkdir -p /app/var/static /app/var/media /app/var/logs /app/var/cache /app/var/tmp \
    && chown -R app:app /app/var

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", \
     "--timeout", "600", "--access-logfile", "-", "--error-logfile", "-"]
