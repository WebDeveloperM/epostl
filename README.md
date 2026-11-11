# Refleksiv portfolio platformasi

Talabalarning pedagogik kompetensiyalarini rivojlantirish, amaliy faoliyatini hujjatlashtirish,
o‘z-o‘zini tahlil qilish va kasbiy rivojlanish dinamikasini kuzatish uchun web-platforma.

**Texnologiyalar:** Python 3.11+ · Django 5.2 LTS · PostgreSQL · Django Templates · Bootstrap 5 ·
Vanilla JavaScript · Chart.js · Django File Storage · Django Authentication.
Alohida React/Vue/Node.js frontend yo‘q — hammasi Django ekotizimida.

---

## 0. Docker orqali ishga tushirish (tavsiya etiladi)

```bash
cp .env.docker.example .env.docker     # parollar va SECRET_KEY ni almashtiring
docker compose up -d --build
```

Platforma: <http://localhost:8080> (port: `PORTFOLIO_PORT=9000 docker compose up -d` bilan o‘zgartiriladi).

* **Mahalliy tarmoq (LAN) orqali kirish:** `.env.docker` dagi `ALLOWED_HOSTS` ga kompyuterning IP manzilini
  (masalan `192.168.2.72`), `CSRF_TRUSTED_ORIGINS` ga esa `http://192.168.2.72:8080` ni qo‘shing va `docker compose up -d`
  qiling — sayt `http://192.168.2.72:8080` da ochiladi (port hamma tarmoq interfeyslarida ochiq; Windows Firewall
  bu portni bloklasa, 8080 uchun kiruvchi qoida qo‘shing). Ro‘yxatda yo‘q host (masalan boshqa IP yoki domen) rad etiladi.
  Docker'siz ishga tushirishda `.env` dagi `ALLOWED_HOSTS` ni to‘ldiring va `python manage.py runserver 0.0.0.0:8000` qiling.
* **Vaqtinchalik internet manzil (boshqa kishiga ko‘rsatish uchun):** kompyuter server bo‘lib qoladi, Cloudflare
  "quick tunnel" `https://<tasodifiy-nom>.trycloudflare.com` manzilini beradi (hisob va domen kerak emas, HTTPS bor).
  Kerak: Docker stack ishlayotgan bo‘lsin va `cloudflared.exe` (`winget install Cloudflare.cloudflared`).
  `powershell -ExecutionPolicy Bypass -File tools\tunnel.ps1 start` — yoqadi va manzilni chiqaradi,
  `... url` — manzilni ko‘rsatadi, `... stop` — o‘chiradi. Manzil har yoqilganda yangi bo‘ladi; kompyuter o‘chsa/uxlasa,
  Docker yoki tunnel to‘xtasa — sayt ochilmaydi. `.env.docker` da `*.trycloudflare.com` allaqachon ruxsat etilgan
  (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`); doimiy o‘z domeningiz kerak bo‘lsa — Cloudflare'da nomlangan tunnel + DNS.
  **Ehtiyot:** manzilni bilgan har kim saytga kira oladi. Demo hisob parollari (`Admin12345!` va b.) ommaviy bo‘lgani
  uchun avval `docker compose exec web python manage.py changepassword admin` bilan administrator parolini
  almashtiring, ko‘rsatish uchun faqat `ustoz`/`talaba1` hisobini bering, ish tugagach `stop` qiling.
* **Mobil versiya:** barcha sahifalar telefon (360 px dan), planshet va kompyuterda ishlaydi: yon menyu surma panel,
  statistika kartalari 2 tadan, ro‘yxat jadvallari telefonda kartaga aylanadi (`table-stack`), diagramma yorliqlari
  ekran kengligiga moslanadi, shakllarda 16 px shrift (iOS yaqinlashtirmaydi), bosish uchun qulay tugmalar.
  Yangi ro‘yxat jadvali qo‘shsangiz, `<table class="table table-hover table-stack">` deb yozing.
* `/` — hamma uchun ochiq **landing (bosh) sahifa**: navbar, banner, slayder, platforma haqida, rivojlanish sikli,
  refleksiya modellari, imkoniyatlar, rollar, savol-javob, chaqiruv va footer; kirish tugmasi `/accounts/login/` ga olib boradi.
  Tizimga kirgan foydalanuvchi navbarda «Boshqaruv panelini ochish» tugmasini ko‘radi.
* **«Administratorga» havolasi:** landing (savol-javob, parol javobi, footer) va kirish sahifasidagi «administratorga
  murojaat qiling» iborasi `.env` dagi `ADMIN_TELEGRAM_URL` (masalan `https://t.me/username`, `@username`) ga olib boradi
  va yangi oynada ochiladi. Bo‘sh yoki yaroqsiz bo‘lsa (faqat `t.me` / `telegram.me` / `telegram.dog`) — oddiy matn.
  Docker'da `.env.docker` ni o‘zgartirgach `docker compose up -d` qiling (`restart` yangi qiymatni o‘qimaydi).
* `/dashboard/` — foydalanuvchining boshqaruv paneli (kirmagan bo‘lsa — login sahifasiga yo‘naltiriladi; URL nomi `dashboard`).
* Landing mazmuni `apps/core/landing.py` da (matnlar tilga qarab), ko‘rinishi `templates/landing.html`,
  `static/css/landing.css`, `static/js/landing.js`. Fayl hajmi chegaralari savol-javobda «Tizim sozlamalari» dan olinadi.

| Servis | Vazifasi |
|---|---|
| `db` | PostgreSQL 17 (`pgdata` volume) |
| `web` | Django + gunicorn; ishga tushganda: bazani kutish → `migrate` → `collectstatic` → administrator (`DJANGO_SUPERUSER_*`) → `SEED_DEMO=1` bo‘lsa demo ma’lumotlar |
| `nginx` | statik fayllar, himoyalangan media (`X-Accel-Redirect`, video uchun Range), katta fayl yuklash (2 GB gacha) |
| `scheduler` | har soatda muddat eslatmalari, kuniga bir marta eskirgan sessiyalarni tozalash |
| `backup` | kunlik `pg_dump` → `./backups/` (oxirgi `KEEP_DAYS` kun) |

Foydali buyruqlar:

```bash
docker compose logs -f web                                   # loglar
docker compose exec web python manage.py createsuperuser     # qo‘shimcha administrator
docker compose run --rm --no-deps -e SKIP_BOOTSTRAP=1 web python manage.py test apps   # testlar (PostgreSQL)
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean /dev/stdin' < backups/db_<sana>.dump
docker compose down        # to‘xtatish (ma’lumotlar saqlanadi);  down -v — volume'lar bilan o‘chirish!
```

Demo ma’lumotlar (`SEED_DEMO=1`) inglizcha yoziladi; kirish: `admin / Admin12345!`, `ustoz / Ustoz12345!`, `talaba1 / Talaba12345!`.

Domen va HTTPS bilan production: `.env.docker` da `SEED_DEMO=0`, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`SITE_URL`
ni domenga moslang, nginx oldiga TLS (certbot yoki tashqi load balancer) qo‘ying va
`SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_HSTS_SECONDS=31536000`.

---

## 1. Lokal ishga tushirish (Docker'siz)

```bash
# 1) Virtual muhit
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt

# 2) PostgreSQL bazasi
psql -U postgres -c "CREATE USER portfolio_user WITH PASSWORD 'kuchli_parol';"
psql -U postgres -c "CREATE DATABASE reflective_portfolio OWNER portfolio_user ENCODING 'UTF8';"

# 3) Sozlamalar: .env.example dan nusxa olib, qiymatlarni to‘ldiring
copy .env.example .env          # Linux: cp .env.example .env
#   DEBUG=True
#   DATABASE_URL=postgres://portfolio_user:kuchli_parol@localhost:5432/reflective_portfolio
#   SECRET_KEY=... (python -c "import secrets; print(secrets.token_urlsafe(50))")

# 4) Jadvallar + boshlang‘ich ma’lumotlar (rollar, 5 kompetensiya, 5 mezon, 5 refleksiya savoli)
python manage.py migrate

# 5a) Demo ma’lumotlar (fakultet, guruh, ustoz, 3 talaba va to‘liq rivojlanish sikli namunasi)
python manage.py seed_demo
#   admin / Admin12345!   ustoz / Ustoz12345!   talaba1..3 / Talaba12345!
# 5b) yoki faqat administrator
python manage.py createsuperuser

python manage.py runserver
```

Brauzerda: <http://127.0.0.1:8000> · Django admin (zaxira panel): `/django-admin/`

### Testlar

```bash
python manage.py test apps
```

89 ta test: har bir rol uchun barcha asosiy sahifalar, RBAC va obyekt darajasidagi ruxsatlar
(talaba boshqa talabaning ishini, faylini, bahosini ko‘ra olmaydi), fayl xavfsizligi (niqoblangan
`.exe`, taqiqlangan kengaytma, ochiq `/media/` yo‘qligi, video uchun HTTP Range), brute-force
himoyasi, Excel import va HTTP orqali to‘liq sikl: topshiriq → yuklash → refleksiya →
qayta ishlash → v2 → tasdiqlash → taqqoslash; ikki tilda ishlash, Gibbs/Kolb refleksiya modellari,
tarjima kataloglarining to‘liqligi, landing sahifa.

---

## 2. Qabul qilish mezonlari (TZ 11-bo‘lim) va ularning bajarilishi

| Mezon | Qayerda |
|---|---|
| Administrator talaba va ustozlarni qo‘shadi | *Foydalanuvchilar* → qo‘lda yoki **Excel import** (namuna fayl yuklab olinadi) |
| Ustoz talabaga topshiriq beradi | *Topshiriqlar → Yangi topshiriq* (guruhga yoki alohida talabalarga) |
| Talaba rivojlanish maqsadini belgilaydi | *Maqsadlarim → Yangi maqsad* |
| Talaba dars rejasini / video / boshqa ishni yuklaydi | Topshiriq sahifasi → *Ish yuklash* (drag-and-drop, bir versiyada bir nechta fayl) |
| Talaba refleksiya savollariga javob beradi | Ish sahifasi → *Refleksiya va yuborish* (qoralama / ustozga yuborish, dalil fayl yoki havola) |
| Ustoz mezonlar asosida baholaydi | *Tekshirish* → ish → *Baholash* (har mezon: ball, izoh, kamchilik, tavsiya) |
| Ustoz ishni qayta ishlashga yuboradi | Baholashda qaror: *Qayta ishlashga qaytarish* |
| Talaba yangi versiya yuklaydi | Ish sahifasi → *Yangi versiya yuklash* — oldingi versiyalar o‘chmaydi |
| Oldingi va keyingi natijalar taqqoslanadi | *Rivojlanishim*, talaba profili (ustoz), maqsad sahifasi, baho sahifasi |
| Har kim faqat o‘ziga tegishli ma’lumotni ko‘radi | Har bir ilovaning `services.visible_*()` funksiyalari; begona obyekt → 404 |

---

## 3. Arxitektura

Modul asosida kengaytiriladigan monolit. Biznes-logika view'larda emas, `services.py` qatlamida.

```
config/            settings.py (.env orqali), urls.py, wsgi.py, asgi.py
apps/
  core/            umumiy qatlam: RBAC mixin'lari, fayl tekshiruvi va himoyalangan uzatish,
                   umumiy CRUD fabrikasi, tizim sozlamalari, grafik spetsifikatsiyalari,
                   seed_demo / generate_erd buyruqlari, testlar
  accounts/        Custom User (users), roles, mentor_assignments, Excel import, kirish himoyasi
  organization/    faculties, departments, directions, groups
  subjects/        subjects
  competencies/    competencies, assessment_criteria
  goals/           goals + rivojlanish sikli holati
  assignments/     assignments, assignment_targets, assignment_attachments, muddat eslatmalari
  portfolios/      portfolios, portfolio_versions, portfolio_files
  reflections/     reflection_questions, reflections, reflection_answers, reflection_evidence
  assessments/     assessments, assessment_details, mentor_feedback
  analytics/       dashboardlar, dastlabki/keyingi natija taqqoslash, dinamika
  notifications/   notifications (+ ixtiyoriy email)
  audit/           audit_logs (kirish/chiqish, yaratish, o‘zgartirish, yuklash, baholash...)
templates/         landing.html (bosh sahifa), base/, accounts/, student/, mentor/, admin/, shared/
static/            css/, js/, images/, vendor/ (Bootstrap 5.3, Bootstrap Icons, Chart.js — oflayn)
deploy/            nginx.conf, gunicorn.service, backup_db.sh, crontab.txt
docs/ERD.md        ma’lumotlar bazasi diagrammasi va barcha maydonlar (modellardan avtomatik)
```

**Ma’lumotlar bazasi:** `docs/ERD.md` — Mermaid ER diagramma, har bir jadvalning maydonlari,
FK/M2M bog‘lanishlari va cheklovlari. Modellar o‘zgarsa: `python manage.py generate_erd`.

### Asosiy dizayn qarorlari

* **Bitta topshiriq — bitta ish, ko‘p versiya.** `portfolios` (talaba+topshiriq bo‘yicha UNIQUE) →
  `portfolio_versions` → `portfolio_files`. Bir versiyaga dars rejasi va dars videosi birga yuklanadi.
  Yuborilgan versiyalar o‘zgarmaydi, hech qachon o‘chirilmaydi.
* **Refleksiya va baho versiyaga bog‘langan** (1:1). Shu sababli har bir iteratsiya tarixi to‘liq saqlanadi.
* **Refleksiya modellari** (`apps/reflections/frameworks.py`): talaba refleksiyani **Gibbs sikli** (6 bosqich:
  tasvir, his-tuyg‘ular, baholash, tahlil, xulosa, harakat rejasi) yoki **Kolb sikli** (4 bosqich: aniq tajriba,
  mulohazali kuzatish, mavhum tushunchalash, faol tajriba qilish) bilan yozadi. Model `reflections.framework` ga yoziladi;
  savollar `reflection_questions.framework/stage` bilan guruhlanadi, javobga bosqich nusxasi
  (`reflection_answers.stage`) saqlanadi. Eski 5 savollik refleksiya «Qisqa refleksiya» (`simple`) bo‘lib qoldi.
  Bir talaba turli ishlarini turli modellar bilan tahlil qilishi mumkin (demo: v1 — Gibbs, v2 — Kolb).
  * **Modelni almashtirish** — faqat qoralama paytida (ustozga yuborilgandan keyin va baholangandan keyin yo‘q).
    Javoblar mos bosqichga ko‘chadi (`CARRY_OVER`: masalan Gibbs «his-tuyg‘ular» + «baholash» → Kolb «mulohazali
    kuzatish»), bir bosqichga tushgan matnlar birlashtiriladi, hech narsa yo‘qolmaydi. Formadagi saqlanmagan
    o‘zgarishlar almashtirishdan oldin saqlanadi.
  * **Asosiy xulosalar** — portfolio sahifasida har bir yuborilgan refleksiyaning oxirgi bosqichlari (Gibbs: xulosa
    + harakat rejasi, Kolb: mavhum tushunchalash + faol tajriba), eskisidan yangisiga.
  * **Modellar bo‘yicha analitika** (`analytics.services.reflection_model_stats`) — talaba analitikasi, ustoz
    «Talabalar» sahifasi va administrator analitikasida: nechta refleksiya, o‘rtacha javob uzunligi (so‘z), o‘rtacha
    ball va bosqichlar bo‘yicha chuqurlik. Ball ishning o‘ziga ham bog‘liq — bu modelning isboti emas, sahifada
    shunday deb yozilgan.
  Administrator savollarni «Baholash tizimi → Refleksiya savollari» da model va bosqich bo‘yicha boshqaradi.
* **Dastlabki va keyingi natija alohida saqlanadi:** `assessments.kind = baseline | work`.
  Boshlang‘ich baholash bo‘lsa — u dastlabki natija, aks holda birinchi baho.
* **Tarixiy yaxlitlik:** `assessment_details.max_score` va `reflection_answers.question_text` — nusxa;
  administrator mezon yoki savolni o‘zgartirsa ham eski natijalar buzilmaydi.
* **Topshiriq holatlari** (`assignment_targets.status`): Yangi → Qabul qilingan → Bajarilmoqda →
  Tekshirishda → Qayta ishlash / Tasdiqlangan; «Muddati o‘tgan» muddat bo‘yicha dinamik aniqlanadi.
* **Siklik bog‘liqlik yo‘q:** `MentorAssignment` — `accounts`da, `AssessmentCriterion` — `competencies`da.

---

## 4. Xavfsizlik (TZ 8-bo‘lim)

| Talab | Amalga oshirilishi |
|---|---|
| Autentifikatsiya | Django Authentication; 5 ta xato urinishdan keyin 15 daqiqa blok; import/yaratilgan foydalanuvchi birinchi kirishda parolni almashtiradi |
| RBAC | `apps/core/permissions.py` — `AdminRequiredMixin`, `MentorRequiredMixin`, `StudentRequiredMixin` |
| Obyekt darajasidagi ruxsat | `visible_portfolios / visible_assessments / visible_reflections / visible_goals / visible_assignments`, `can_assess` |
| CSRF / XSS | Django CSRF middleware, shablonlarda avtomatik escaping, `X-Content-Type-Options: nosniff` |
| SQL Injection | faqat Django ORM |
| Fayl tekshiruvi | kengaytma oq ro‘yxati + fayl imzosi bo‘yicha haqiqiy MIME (`filetype`) + hajm limiti (administrator sozlaydi) |
| Fayllar ochiq URL orqali berilmaydi | `/media/` xizmat qilinmaydi; tasodifiy nomlar; ruxsat tekshirilgach `X-Accel-Redirect` (nginx `internal`) |
| Parol xeshlash | Django PBKDF2 (standart) |
| Audit log | `audit_logs` jadvali + *Audit log* sahifasi (filtr: foydalanuvchi, amal, sana) |
| Zaxira nusxa | `deploy/backup_db.sh` (kunlik `pg_dump`, haftalik media) |
| HTTPS | `DEBUG=False` da: SSL redirect, HSTS, secure cookie; nginx + certbot |
| Maxfiy sozlamalar | `.env` (`django-environ`) |

---

## 5. Serverga joylashtirish (Ubuntu)

```bash
sudo apt install python3.11-venv postgresql nginx
sudo useradd -m -d /opt/reflective_portfolio portfolio
# kodni /opt/reflective_portfolio ga joylang, .env ni to‘ldiring (DEBUG=False, PROTECTED_MEDIA_USE_X_ACCEL=True)
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py check --deploy

sudo cp deploy/gunicorn.service /etc/systemd/system/reflective_portfolio.service
sudo systemctl enable --now reflective_portfolio
sudo cp deploy/nginx.conf /etc/nginx/sites-available/reflective_portfolio
sudo ln -s /etc/nginx/sites-available/reflective_portfolio /etc/nginx/sites-enabled/
sudo certbot --nginx -d portfolio.example.uz
crontab -u portfolio deploy/crontab.txt     # muddat eslatmalari, kunlik backup, sessiyalarni tozalash
```

* Bir nechta gunicorn worker uchun umumiy kesh tavsiya etiladi (`CACHE_URL=filecache://...` yoki Redis) —
  kirish urinishlari hisobi va tizim sozlamalari keshi barcha worker'larda bir xil bo‘lishi uchun.
* Katta videolar: nginx `client_max_body_size` tizim sozlamalaridagi video limitidan katta bo‘lsin.
* Excel import 1000 qatorgacha; har bir parol xeshlanadi, shuning uchun katta fayl bir necha daqiqa olishi mumkin
  (gunicorn `--timeout 600`).

---

## 6. Til (English / O‘zbekcha)

Sayt ikki tilda ishlaydi. **Asosiy til — ingliz tili** (oddiy, boshlang‘ich darajadagi so‘zlar bilan);
yuqori paneldagi **globus tugmasi** (qo‘ng‘iroqchaning chap tomonida; kirish sahifasida — yuqori o‘ng burchakda)
orqali o‘zbek tiliga o‘tiladi.

* Faol til: 1) shu brauzerdagi cookie (`portfolio_language`), 2) tizimga kirgan foydalanuvchining saqlangan tili
  (`users.language`, yangi qurilmada), 3) `LANGUAGE_CODE="en"`. Brauzerning `Accept-Language` sarlavhasi ataylab
  e’tiborga olinmaydi — asosiy til brauzer sozlamasiga qarab o‘zgarib ketmasin.
* Tanlov foydalanuvchi profiliga ham yoziladi: bildirishnomalar **qabul qiluvchining** tilida yaratiladi
  (`notify(title=lambda: _("...") % {...})` — funksiya har bir qabul qiluvchi tilida chaqiriladi).
* Kodda matnlar (msgid) o‘zbek tilida yozilgan; `locale/en/LC_MESSAGES/django.po` ularni oddiy inglizchaga o‘giradi.
  `locale/uz/...` — matn o‘zi bilan (**shart**: bo‘lmasa asosiy til inglizcha bo‘lgani uchun Django topilmagan matnni
  inglizcha katalogdan olib qo‘yadi). Ikkala katalogdagi matnlar to‘plami bir xil bo‘lishi `CatalogTests` da tekshiriladi.
* Bazadagi standart nomlar (kompetensiya, mezon, refleksiya savollari, platforma nomi) joriy tilga `tr()` / `|tr`
  orqali o‘giriladi; ular `apps/core/translatable_data.py` da katalogga kiritilgan. Administrator o‘zgartirgan nom
  tarjimasiz, yozilganidek ko‘rsatiladi.
* Demo ma’lumotlar (`seed_demo`) inglizcha yoziladi.

Yangi matn qo‘shganingizda (GNU gettext **kerak emas**, Windows'da ham ishlaydi):

```bash
python tools/catalog.py check            # kodda bor, lekin katalogda yo‘q matnlarni ko‘rsatadi
# yangi.json:  {"O‘zbekcha matn": "Simple English text", ...}
python tools/catalog.py add yangi.json   # matnlarni locale/en (tarjima) va locale/uz (o‘zi bilan) ga qo‘shadi va .mo ni yig‘adi
python tools/catalog.py compile          # faqat .po fayllarni qo‘lda tahrirlagan bo‘lsangiz: .mo ni qayta yig‘ish
python manage.py test apps.core.tests.CatalogTests   # to‘liqlik, o‘rinbosarlar va «kodda ishlatilgan har bir matn katalogda bor»
```

GNU gettext o‘rnatilgan bo‘lsa, odatdagi `makemessages` / `compilemessages` ham ishlaydi.

Til qo‘shish (masalan, rus): `LANGUAGES` ga qo‘shing, `locale/ru` yarating va `portfolio_language` cookie / `users.language`
qiymatlari avtomatik ishlaydi.

## 7. Keyingi bosqich (TZ 12-bo‘lim)

AI video tahlili, nutq tezligi, savollar sonini hisoblash, refleksiya matnini AI tahlili va PDF portfolio
hisoboti uchun tayyor nuqtalar: `portfolio_files` (media metama’lumotlari), `reflection_answers` (matnlar),
`assessment_details` (mezonlar bo‘yicha tarix) va `services.py` qatlami.
