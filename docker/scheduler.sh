#!/bin/sh
# Muddat eslatmalari (har soatda) va eskirgan sessiyalarni tozalash (kuniga bir marta).
set -e
i=0
while true; do
    python manage.py process_deadlines || echo "[scheduler] process_deadlines xatosi"
    if [ $((i % 24)) -eq 0 ]; then
        python manage.py clearsessions || true
    fi
    i=$((i + 1))
    sleep "${SCHEDULER_INTERVAL:-3600}"
done
