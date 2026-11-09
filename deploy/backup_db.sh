#!/usr/bin/env bash
# Kunlik PostgreSQL zaxira nusxasi (cron orqali). Oxirgi $KEEP_DAYS kunlik nusxalar saqlanadi.
#   0 2 * * * /opt/reflective_portfolio/deploy/backup_db.sh >> /var/log/reflective_portfolio/backup.log 2>&1
set -euo pipefail

DB_NAME="${DB_NAME:-reflective_portfolio}"
DB_USER="${DB_USER:-portfolio_user}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/reflective_portfolio}"
MEDIA_DIR="${MEDIA_DIR:-/var/www/reflective_portfolio/media}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Parol ~/.pgpass faylida saqlanadi (chmod 600)
pg_dump -U "$DB_USER" -h localhost -Fc "$DB_NAME" > "$BACKUP_DIR/db_$STAMP.dump"
echo "$(date -Is) DB zaxira: $BACKUP_DIR/db_$STAMP.dump"

# Media fayllar (videolar katta bo‘lishi mumkin) — haftada bir marta to‘liq nusxa
if [ "$(date +%u)" = "7" ]; then
    tar -czf "$BACKUP_DIR/media_$STAMP.tar.gz" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
    echo "$(date -Is) Media zaxira: $BACKUP_DIR/media_$STAMP.tar.gz"
fi

find "$BACKUP_DIR" -name 'db_*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'media_*.tar.gz' -mtime +$((KEEP_DAYS * 4)) -delete

# Tiklash: pg_restore -U "$DB_USER" -h localhost -d "$DB_NAME" --clean "$BACKUP_DIR/db_<sana>.dump"
