#!/bin/sh
# Kunlik PostgreSQL zaxira nusxasi (postgres image ichida ishlaydi).
# Nusxalar ./backups papkasiga yoziladi, oxirgi $KEEP_DAYS kunlik saqlanadi.
set -e
mkdir -p /backups
# Birinchi nusxa migratsiyalar tugagach olinsin
sleep "${BACKUP_START_DELAY:-300}"
while true; do
    stamp=$(date +%Y-%m-%d_%H%M)
    if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "/backups/db_$stamp.dump.part"; then
        mv "/backups/db_$stamp.dump.part" "/backups/db_$stamp.dump"
        echo "[backup] $(date -Iseconds) tayyor: db_$stamp.dump"
    else
        rm -f "/backups/db_$stamp.dump.part"
        echo "[backup] $(date -Iseconds) XATO"
    fi
    find /backups -name 'db_*.dump' -mtime +"${KEEP_DAYS:-14}" -delete
    sleep "${BACKUP_INTERVAL:-86400}"
done
