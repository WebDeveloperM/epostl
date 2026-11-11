"""Video qo'llanma sahnalari: diktor matni + brauzerdagi harakatlar.

    python -I record.py dry     # tez sinov (ovoz kutilmaydi, kadr yozilmaydi) — selektorlarni tekshirish
    python -I record.py real    # haqiqiy yozuv
    python -I record.py build   # oxirgi yozuvdan videoni yig'ish
"""
import asyncio
import json
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import engine  # noqa: E402
from engine import BASE, BUILD, CURSOR_JS, DSF, VH, VW, Scene, build_video  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SAMPLES = ROOT / "samples"
DATA = ROOT / "data"
OUT = ROOT / "output"
PW = {"talaba1": "Talaba12345!", "ustoz": "Ustoz12345!", "admin": "Admin12345!"}
TODAY = date.today()


def reset_db():
    shutil.copy(DATA / "seed.sqlite3", DATA / "video.sqlite3")
    if (DATA / "media").exists():
        shutil.rmtree(DATA / "media")
    shutil.copytree(DATA / "media_seed", DATA / "media")


async def new_page(browser, user=None, cursor=True):
    ctx = await browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, locale="uz-UZ")
    await ctx.add_cookies([{"name": "portfolio_language", "value": "uz", "url": BASE}])
    if cursor:
        await ctx.add_init_script(CURSOR_JS)
    page = await ctx.new_page()
    page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    if user:
        await page.goto(BASE + "/accounts/login/")
        await page.fill("input[name=username]", user)
        await page.fill("input[name=password]", PW[user])
        async with page.expect_navigation():
            await page.click(".auth-form form[novalidate] button[type=submit]")
    return page


async def goto(page, path):
    await page.goto(BASE + path)
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(300)


async def pick(sc, loc, text):
    """Select ichidan matni `text` ni o'z ichiga olgan variantni tanlaydi."""
    val = await loc.first.evaluate(
        "(el, s) => { const o=[...el.options].find(o=>o.text.toLowerCase().includes(s.toLowerCase())); return o?o.value:null }",
        text)
    assert val is not None, f"variant topilmadi: {text}"
    await sc.select(loc, value=val)


# --------------------------------------------------------------- kartalar ---
def card_html(kicker, title, subtitle="", chips=()):
    chips_html = "".join(f'<span class="chip" style="animation-delay:{0.45 + i * 0.08:.2f}s">{c}</span>'
                         for i, c in enumerate(chips))
    return f"""<!doctype html><html lang="uz"><head><meta charset="utf-8"><style>
html,body{{margin:0;height:100%;overflow:hidden;font-family:'Segoe UI',system-ui,sans-serif}}
body{{color:#fff;display:flex;align-items:center;justify-content:center;
 background:radial-gradient(900px 520px at 85% -10%,rgba(255,255,255,.16),transparent 60%),
 radial-gradient(700px 500px at -10% 110%,rgba(99,102,241,.35),transparent 60%),
 linear-gradient(135deg,#0f172a 0%,#1e2a78 55%,#4154f1 100%)}}
.wrap{{text-align:center;max-width:1040px;padding:0 48px}}
.wrap>*{{opacity:0}}
body.go .wrap>*, body.go .chip{{animation:up .7s cubic-bezier(.2,.7,.2,1) both}}
.logo{{width:76px;height:76px;margin:0 auto 22px;display:block}}
.kicker{{font-size:19px;letter-spacing:.2em;text-transform:uppercase;color:#c7d2fe;font-weight:600}}
h1{{font-size:60px;line-height:1.12;margin:.28em 0 .22em;font-weight:700}}
p{{font-size:25px;color:#e0e7ff;margin:0 0 34px}}
.chips{{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;opacity:1 !important;animation:none !important}}
.chip{{opacity:0;padding:9px 20px;border-radius:999px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);
 font-size:19px;font-weight:600}}
@keyframes up{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:none}}}}
</style></head><body><div class="wrap">
<img class="logo" style="animation-delay:0s" src="{BASE}/static/images/logo-light.svg" alt="">
<div class="kicker" style="animation-delay:.1s">{kicker}</div>
<h1 style="animation-delay:.2s">{title}</h1>
{f'<p style="animation-delay:.3s">{subtitle}</p>' if subtitle else ''}
<div class="chips">{chips_html}</div>
</div></body></html>"""


async def card(browser, name, html, *texts, hold=0.6):
    page = await new_page(browser, cursor=False)
    await page.set_content(html, wait_until="load")
    sc = Scene(name, page)
    await sc.start(fade=False)
    await page.evaluate("document.body.classList.add('go')")
    await sc.pause(0.5)
    for t in texts:
        async with sc.beat(t, gap=0.3):
            pass
    await sc.pause(hold)
    res = await sc.end()
    await page.context.close()
    return res


# ------------------------------------------------------------ bosh sahifa ---
async def landing(browser):
    page = await new_page(browser)
    await goto(page, "/")
    sc = Scene("landing", page)
    await sc.start()
    async with sc.beat("Saytni ochganingizda bosh sahifa chiqadi. Unda platforma haqida ma’lumot, rivojlanish sikli, "
                       "refleksiya modellari va ko‘p beriladigan savollarga javoblar bor."):
        await sc.pause(1.2)
        for sel in ("#about", "#cycle", "#models", "#roles", "#faq"):
            await sc.scroll_into(page.locator(sel), 0.08, 1.1)
            await sc.pause(0.9)
        await sc.scroll_to(0, 1.2)
    async with sc.beat("Tizimga kirish uchun «Kirish» tugmasini bosing."):
        btn = page.locator(".lp-navbar a.btn", has_text="Kirish")
        await sc.hover(btn, 0.8)
        await sc.at("bosing")
        await sc.click(btn, 0.2, nav=True)
    async with sc.beat("Til tugmasi orqali o‘zbek yoki ingliz tilini tanlash mumkin."):
        lang = page.locator(".auth-lang button.icon-btn")
        await sc.click(lang, 0.7)
        await sc.pause(0.5)
        await sc.hover(page.locator(".auth-lang .dropdown-item").first, 0.5)
        await sc.pause(0.5)
        await sc.hover(page.locator(".auth-lang .dropdown-item").last, 0.4)
        await sc.pause(0.9)
        await page.keyboard.press("Escape")
    async with sc.beat("Login va parolni administrator beradi. Ularni kiriting va «Kirish» tugmasini bosing."):
        await sc.type(page.locator("input[name=username]"), "talaba1", cps=9)
        await sc.type(page.locator("input[name=password]"), PW["talaba1"], cps=16)
        await sc.at("bosing")
        await sc.click(page.locator(".auth-form form[novalidate] button[type=submit]"), 0.5, nav=True)
    async with sc.beat("Birinchi kirishda tizim parolni yangisiga almashtirishni so‘raydi."):
        await sc.hover(page.locator(".profile-chip"), 1.2)
    res = await sc.end()
    await page.context.close()
    return res


# ----------------------------------------------------------------- talaba ---
GIBBS = [
    "3-sinfda «Suv va uning xossalari» mavzusida dars o‘tdim. «Aqliy hujum» va juftlikda tajriba usullaridan foydalandim.",
    "Dars boshida biroz hayajonlandim, o‘quvchilar faol qatnashgach, o‘zimni ishonchli his qildim.",
    "Juftlikdagi tajriba yaxshi chiqdi: deyarli barcha o‘quvchilar qatnashdi. «Klaster» bosqichiga vaqt yetmadi.",
    "Tajriba bosqichi rejadagidan uzoq davom etdi, chunki ko‘rsatmalarni oldindan tayyorlamagan edim.",
    "Interfaol metodlar o‘quvchilarni faollashtiradi, lekin aniq vaqt rejasi zarur.",
    "Keyingi darsda har bir bosqichga taymer qo‘yaman va ko‘rsatma kartalarini oldindan tayyorlayman.",
]


async def student(browser):
    page = await new_page(browser, "talaba1")
    await goto(page, "/dashboard/")
    sc = Scene("student", page)
    await sc.start()
    async with sc.beat("Talaba panelida portfolio holati, maqsadlar, faol topshiriqlar va kompetensiyalar bo‘yicha "
                       "rivojlanish grafigi ko‘rinadi."):
        await sc.at("portfolio")
        await sc.highlight(*[page.locator(".stat-card").nth(i) for i in range(4)])
        await sc.hover(page.locator(".stat-card").nth(0), 0.6)
        await sc.at("kompetensiyalar")
        await sc.clear()
        chart = page.locator(".card", has=page.locator(".card-header", has_text="Kompetensiyalar bo‘yicha"))
        await sc.highlight(chart.locator(".card-header"), chart.locator("canvas"))
        await sc.hover(chart.locator("canvas"), 0.7)
    async with sc.beat("Chap tomondagi menyuda rivojlanish siklining barcha bo‘limlari joylashgan."):
        await sc.clear()
        await sc.highlight(sc.side("Maqsadlarim"), sc.side("Rivojlanishim"), pad=4)
        await sc.hover(sc.side("Maqsadlarim"), 0.8)
    async with sc.beat("Ishni maqsad qo‘yishdan boshlang. «Maqsadlarim» bo‘limida «Yangi maqsad» tugmasini bosing."):
        await sc.clear()
        await sc.at("«Maqsadlarim»")
        await sc.click(sc.side("Maqsadlarim"), 0.4, nav=True)
        await sc.at("tugmasini")
        await sc.click(page.locator(".app-content a.btn", has_text="Yangi maqsad"), 0.8, nav=True)
    async with sc.beat("Maqsad nomini, rivojlantiriladigan kompetensiyani, tugash muddatini va kutilayotgan natijani "
                       "yozib, saqlang."):
        await sc.type(page.locator("#id_title"), "Darsda interfaol metodlarni samarali qo‘llash", cps=30)
        await pick(sc, page.locator("#id_competency"), "muloqot")
        await sc.fill(page.locator("#id_target_date"), (TODAY + timedelta(days=60)).isoformat())
        await sc.type(page.locator("#id_expected_outcome"),
                      "Har bir darsda kamida ikkita interfaol metod qo‘llanadi.", cps=36)
    async with sc.beat("Maqsad saqlandi. Endi ishlaringizni unga bog‘lash mumkin."):
        await sc.click(page.locator("form button[type=submit]", has_text="Saqlash"), 0.6, nav=True)
    async with sc.beat("«Topshiriqlar» bo‘limida ustoz bergan vazifalar turadi. Yangi topshiriqni ochib, uning "
                       "shartlari va muddati bilan tanishing."):
        await sc.click(sc.side("Topshiriqlar"), 0.6, nav=True)
        await sc.at("ochib")
        await sc.click(page.locator(".app-content a", has_text="Interfaol metodlar asosida dars loyihasi"), 0.6, nav=True)
        await sc.pause(0.8)
        await sc.scroll_by(260, 1.0)
        await sc.pause(1.0)
        await sc.scroll_to(0, 0.8)
    async with sc.beat("So‘ng «Topshiriqni qabul qilish» tugmasini bosing va ishingizni yuklang."):
        await sc.click(page.locator("button", has_text="Topshiriqni qabul qilish"), 0.7, nav=True)
        await sc.at("yuklang")
        await sc.click(page.locator(".app-content a.btn", has_text="ish yuklash"), 0.6, nav=True)
    async with sc.beat("Ish nomini yozing, uni maqsadingizga bog‘lang va material turini tanlang."):
        await sc.type(page.locator("#id_title"), "Interfaol dars: «Suv va uning xossalari»", cps=30)
        await pick(sc, page.locator("#id_goal"), "interfaol")
        await pick(sc, page.locator("#id_material_type"), "Dars ishlanmasi")
    async with sc.beat("Fayllarni shu maydonga sudrab tashlang yoki bosib tanlang. Bitta versiyaga dars ishlanmasi va "
                       "dars videosini birga yuklash mumkin."):
        zone = page.locator(".dropzone").first
        await sc.scroll_into(zone, 0.25, 0.8)
        await sc.hover(zone, 0.6)
        await zone.evaluate("z => z.classList.add('dragover')")
        await sc.pause(0.9)
        await page.locator("input[type=file][name=files]").set_input_files(
            [str(SAMPLES / "Interfaol_dars_loyihasi.pdf"), str(SAMPLES / "Dars_videosi.mp4")])
        await zone.evaluate("z => z.classList.remove('dragover')")
        await sc.at("Bitta")
        await sc.highlight(page.locator(".dz-files"))
    async with sc.beat("So‘ng «Yuklash» tugmasini bosing."):
        await sc.clear()
        await sc.click(page.locator("form button[type=submit]", has_text="Yuklash"), 0.6, nav=True)
    async with sc.beat("Ish sahifasi ochildi. Endi refleksiya yozib, ishni ustozga yuborish kerak."):
        btn = page.locator(".app-content a.btn", has_text="Refleksiya va yuborish")
        await sc.at("refleksiya")
        await sc.highlight(btn)
        await sc.hover(btn, 0.7)
        await sc.pause(0.6)
        await sc.clear()
        await sc.click(btn, 0.2, nav=True)
    async with sc.beat("Refleksiya ikki modeldan biri asosida yoziladi: Gibbs sikli olti bosqichdan, Kolb sikli esa to‘rt "
                       "bosqichdan iborat. O‘zingizga qulay modelni tanlang."):
        cards = page.locator(".model-card")
        await sc.at("Gibbs")
        await sc.highlight(cards.nth(0))
        await sc.at("Kolb")
        await sc.clear()
        await sc.highlight(cards.nth(1))
        await sc.at("tanlang")
        await sc.clear()
        await sc.click(page.locator("a[href*='model=gibbs']"), 0.7, nav=True)
    async with sc.beat("Har bir bosqich savoliga o‘z tajribangizga tayanib javob yozing. Yuqoridagi chiziq nechta "
                       "savolga javob berilganini ko‘rsatadi.", gap=0.2):
        qs = page.locator("textarea[name^=q_]")
        await sc.scroll_into(qs.nth(0), 0.35, 0.7)
        await sc.type(qs.nth(0), GIBBS[0], cps=45)
        for i in range(1, 6):
            await sc.scroll_into(qs.nth(i), 0.45, 0.45)
            await sc.fill(qs.nth(i), GIBBS[i], 0.3)
            await sc.pause(0.15)
        await sc.scroll_to(0, 0.9)
        await sc.highlight(page.locator("[data-reflection-progress]"))
    async with sc.beat("Javoblarni qoralama sifatida saqlash yoki darhol «Ustozga yuborish» mumkin."):
        await sc.clear()
        await sc.at("qoralama")
        await sc.highlight(page.locator("button[name=action][value=draft]"))
        await sc.hover(page.locator("button[name=action][value=draft]"), 0.6)
        await sc.at("«Ustozga")
        await sc.clear()
        await sc.click(page.locator("button[name=action][value=submit]"), 0.5, nav=True)
    async with sc.beat("Ustoz baholagach, «Baholarim» bo‘limida har bir mezon bo‘yicha ball, kamchiliklar va "
                       "tavsiyalarni ko‘rasiz."):
        await sc.click(sc.side("Baholarim"), 0.6, nav=True)
        await sc.click(page.locator(".app-content a", has_text="63/100"), 0.7, nav=True)
        await sc.scroll_by(330, 1.2)
    async with sc.beat("Ish qayta ishlashga qaytarilsa, yangi versiya yuklaysiz. Oldingi versiyalar va baholar "
                       "tarixda saqlanadi."):
        await sc.click(sc.side("Portfolio"), 0.6, nav=True)
        await sc.click(page.locator(".app-content a", has_text="Savol-javob darsi: «Tabiat»"), 0.6, nav=True)
        hist = page.locator(".card", has=page.locator(".card-header", has_text="Versiyalar tarixi"))
        await sc.at("Oldingi")
        await sc.scroll_into(hist, 0.2, 1.0)
        await sc.highlight(hist)
    async with sc.beat("«Rivojlanishim» sahifasida boshlang‘ich va keyingi natijalar grafiklarda taqqoslanadi."):
        await sc.clear()
        await sc.click(sc.side("Rivojlanishim"), 0.6, nav=True)
        await sc.pause(1.0)
        await sc.scroll_by(420, 1.4)
        await sc.pause(1.2)
        await sc.scroll_by(420, 1.4)
    res = await sc.end()
    await page.context.close()
    return res


# ------------------------------------------------------------------ ustoz ---
async def mentor(browser):
    page = await new_page(browser, "ustoz")
    await goto(page, "/dashboard/")
    sc = Scene("mentor", page)
    await sc.start()
    async with sc.beat("Ustoz panelida biriktirilgan talabalar, tekshirish kutilayotgan ishlar va talabalarning "
                       "rivojlanish ko‘rsatkichlari jamlangan."):
        await sc.highlight(*[page.locator(".stat-card").nth(i) for i in range(4)])
        await sc.hover(page.locator(".stat-card").nth(0), 0.6)
        await sc.at("tekshirish")
        await sc.clear()
        await sc.highlight(page.locator(".card", has=page.locator(".card-header", has_text="Tekshirish kutilayotgan")))
        await sc.at("rivojlanish")
        await sc.clear()
        await sc.hover(page.locator("canvas").first, 0.7)
    async with sc.beat("Yangi topshiriq berish uchun «Topshiriq berish» tugmasini bosing."):
        await sc.at("bosing")
        await sc.click(page.locator(".app-content a.btn", has_text="Topshiriq berish"), 0.6, nav=True)
    async with sc.beat("Topshiriq nomi va tavsifini yozing, fan va kompetensiyani tanlang."):
        await sc.type(page.locator("#id_title"), "Darsda vaqtni boshqarish: 45 daqiqalik dars rejasi", cps=32)
        await sc.type(page.locator("#id_description"),
                      "Har bir bosqichga aniq vaqt ajratilgan dars rejasini tuzing.", cps=40)
        await pick(sc, page.locator("#id_subject"), "metodikasi")
        await pick(sc, page.locator("#id_competency"), "rejalashtirish")
    async with sc.beat("Baholash mezonlari va muddatni belgilang."):
        crit = page.locator("input[name=criteria]")
        await sc.scroll_into(crit.nth(0), 0.3, 0.8)
        for i in (0, 1, 4):
            await sc.click(crit.nth(i), 0.4)
        await sc.fill(page.locator("#id_due_date"), (TODAY + timedelta(days=14)).isoformat() + "T18:00", 0.6)
    async with sc.beat("So‘ng guruhni yoki alohida talabalarni tanlab, «Topshiriqni yuborish» tugmasini bosing. "
                       "Talabalarga bildirishnoma boradi."):
        await sc.click(page.locator("input[name=groups]").first, 0.6)
        await sc.at("«Topshiriqni")
        await sc.click(page.locator("button", has_text="Topshiriqni yuborish"), 0.6, nav=True)
    async with sc.beat("Talabalar yuborgan ishlar «Tekshirish» bo‘limiga tushadi. Ishni ochib, yuklangan fayllar va "
                       "talaba refleksiyasi bilan tanishing."):
        await sc.click(sc.side("Tekshirish"), 0.6, nav=True)
        await sc.at("ochib")
        await sc.click(page.locator("tr", has_text="Karimov").locator("a.btn"), 0.7, nav=True)
        await sc.pause(0.6)
        await sc.scroll_by(380, 1.3)
    async with sc.beat("So‘ng «Baholash» tugmasini bosing."):
        await sc.scroll_to(0, 0.7)
        await sc.click(page.locator("a.btn-primary[href*='/assessments/version/']"), 0.6, nav=True)
    async with sc.beat("Har bir mezon bo‘yicha ball qo‘ying, kerak bo‘lsa kamchilik va tavsiya yozing. Jami ball "
                       "avtomatik hisoblanadi.", gap=0.2):
        scores = page.locator("input[data-score-input]")
        await sc.type(scores.nth(0), "15", cps=6)
        await sc.type(page.locator("[name^=weaknesses_]").nth(0), "Klaster bosqichiga vaqt yetmagan", cps=34)
        await sc.type(page.locator("[name^=recommendations_]").nth(0), "Har bir bosqichga taymer qo‘ying", cps=34)
        for i, v in enumerate(("16", "17", "16", "15"), start=1):
            await sc.type(scores.nth(i), v, cps=8)
        await sc.highlight(page.locator("[data-score-total]"))
    async with sc.beat("Oxirida xulosa yozib, qaror tanlang: ishni tasdiqlash yoki qayta ishlashga qaytarish."):
        await sc.clear()
        await sc.type(page.locator("#id_overall_comment"), "Interfaol metodlar yaxshi tanlangan. Ish tasdiqlandi.",
                      cps=40)
        await sc.at("qayta")
        await sc.hover(page.locator("input[name=decision][value=revision]"), 0.5)
        await sc.pause(0.4)
        await sc.click(page.locator("input[name=decision][value=approved]"), 0.5)
        await sc.click(page.locator("button", has_text="Bahoni saqlash"), 0.6, nav=True)
    async with sc.beat("«Mening talabalarim» bo‘limida har bir talabaning maqsadlari, ishlari va natijalar dinamikasi "
                       "ko‘rinadi. Bu yerda boshlang‘ich baholashni ham o‘tkazish mumkin."):
        await sc.click(sc.side("Mening talabalarim"), 0.6, nav=True)
        await sc.click(page.locator(".app-content a", has_text="Karimov Aziz"), 0.7, nav=True)
        await sc.pause(0.6)
        await sc.scroll_by(420, 1.4)
        await sc.at("boshlang‘ich")
        await sc.scroll_to(0, 0.8)
        btn = page.locator(".app-content a.btn", has_text="Boshlang‘ich baholash")
        await sc.highlight(btn)
        await sc.hover(btn, 0.6)
    res = await sc.end()
    await page.context.close()
    return res


# ---------------------------------------------------------- administrator ---
async def admin(browser):
    page = await new_page(browser, "admin")
    await goto(page, "/dashboard/")
    sc = Scene("admin", page)
    await sc.start()
    async with sc.beat("Administrator panelida platformaning umumiy holati ko‘rinadi: foydalanuvchilar, fakultetlar, "
                       "topshiriqlar va so‘nggi faollik."):
        await sc.highlight(*[page.locator(".stat-card").nth(i) for i in range(7)])
        await sc.hover(page.locator(".stat-card").nth(0), 0.6)
        await sc.at("faollik")
        await sc.clear()
        await sc.scroll_by(300, 1.0)
    async with sc.beat("«Foydalanuvchilar» bo‘limida talaba va ustozlar qo‘shiladi. «Yangi foydalanuvchi» tugmasi "
                       "orqali bittadan qo‘shish mumkin."):
        await sc.click(sc.side("Foydalanuvchilar"), 0.6, nav=True)
        await sc.at("«Yangi")
        await sc.click(page.locator(".app-content a.btn", has_text="Yangi foydalanuvchi"), 0.6, nav=True)
        await sc.pause(0.6)
        await sc.scroll_by(300, 1.0)
    async with sc.beat("Ko‘p foydalanuvchini Excel orqali import qilish qulayroq. Namuna faylni yuklab oling, "
                       "to‘ldiring va qayta yuklang. Parol yozilmasa, tizim uni o‘zi yaratadi."):
        await sc.click(sc.side("Foydalanuvchilar"), 0.5, nav=True)
        await sc.click(page.locator(".app-content a.btn", has_text="Excel orqali import"), 0.6, nav=True)
        await sc.at("Namuna")
        btn = page.locator(".app-content a.btn", has_text="Namuna faylni yuklab olish")
        await sc.highlight(btn)
        await sc.hover(btn, 0.6)
        await sc.at("qayta")
        await sc.clear()
        await sc.highlight(page.locator("button", has_text="Import qilish"))
        await sc.at("Parol")
        await sc.clear()
        await sc.highlight(page.locator(".card", has=page.locator(".card-header", has_text="Fayl tuzilmasi")))
    async with sc.beat("«Ustoz biriktiruvlari» bo‘limida ustoz guruhga yoki alohida talabaga biriktiriladi. Ustoz "
                       "faqat o‘ziga biriktirilgan talabalarni ko‘radi."):
        await sc.clear()
        await sc.click(sc.side("Ustoz biriktiruvlari"), 0.6, nav=True)
        await sc.hover(page.locator("table tbody tr").first, 0.7)
    async with sc.beat("Tashkiliy tuzilma bo‘limida fakultetlar, kafedralar, yo‘nalishlar, guruhlar va fanlar "
                       "boshqariladi."):
        await sc.at("fakultetlar")
        await sc.click(sc.side("Fakultetlar"), 0.5, nav=True)
        await sc.at("guruhlar")
        await sc.click(sc.side("Guruhlar"), 0.5, nav=True)
    async with sc.beat("Baholash tizimida kompetensiyalar, mezonlar hamda Gibbs va Kolb refleksiya savollari "
                       "sozlanadi."):
        await sc.click(sc.side("Kompetensiyalar"), 0.5, nav=True)
        await sc.at("mezonlar")
        await sc.click(sc.side("Baholash mezonlari"), 0.5, nav=True)
        await sc.at("Gibbs")
        await sc.click(sc.side("Refleksiya savollari"), 0.5, nav=True)
    async with sc.beat("«Analitika» sahifasida butun platforma bo‘yicha natijalar va statistika ko‘rinadi."):
        await sc.click(sc.side("Analitika"), 0.6, nav=True)
        await sc.pause(0.8)
        await sc.scroll_by(450, 1.4)
        await sc.pause(1.0)
        await sc.scroll_by(450, 1.4)
    async with sc.beat("«Audit log» kim, qachon va qanday amal bajarganini qayd etib boradi."):
        await sc.click(sc.side("Audit log"), 0.6, nav=True)
        await sc.hover(page.locator("table tbody tr").first, 0.6)
    async with sc.beat("«Tizim sozlamalari»da platforma nomi, fayl hajmi chegaralari va muddat eslatmalari "
                       "sozlanadi."):
        await sc.click(sc.side("Tizim sozlamalari"), 0.6, nav=True)
        await sc.pause(0.6)
        await sc.hover(page.locator(".app-content input[name=max_upload_size_mb]"), 0.8)
    res = await sc.end()
    await page.context.close()
    return res


# ----------------------------------------------------------------- asosiy ---
INTRO = "Assalomu alaykum! Ushbu video qo‘llanmada «Refleksiv portfolio» platformasidan talaba, ustoz va " \
        "administrator sifatida qanday foydalanishni ko‘rib chiqamiz."
OUTRO = "Maqsad qo‘yish, ish yuklash, refleksiya, baholash va rivojlanishni kuzatish — barchasi bitta " \
        "platformada. Savollar bo‘lsa, administratorga murojaat qiling. E’tiboringiz uchun rahmat!"


async def record(only=None):
    reset_db()
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        steps = [
            ("intro", lambda: card(browser, "c0_intro", card_html(
                "Video qo‘llanma", "Refleksiv portfolio", "Platformadan foydalanish bo‘yicha to‘liq qo‘llanma",
                ["Talaba", "Ustoz", "Administrator"]), INTRO)),
            ("landing", lambda: landing(browser)),
            ("c1", lambda: card(browser, "c1_student", card_html(
                "1-qism", "Talaba", "", ["Maqsad", "Topshiriq", "Ish yuklash", "Refleksiya", "Baholar",
                                         "Rivojlanish"]), "Birinchi qism: talaba.")),
            ("student", lambda: student(browser)),
            ("c2", lambda: card(browser, "c2_mentor", card_html(
                "2-qism", "Ustoz", "", ["Topshiriq berish", "Tekshirish", "Baholash", "Talabalar dinamikasi"]),
                "Ikkinchi qism: ustoz.")),
            ("mentor", lambda: mentor(browser)),
            ("c3", lambda: card(browser, "c3_admin", card_html(
                "3-qism", "Administrator", "", ["Foydalanuvchilar", "Excel import", "Tuzilma", "Baholash tizimi",
                                                "Analitika", "Sozlamalar"]), "Uchinchi qism: administrator.")),
            ("admin", lambda: admin(browser)),
            ("outro", lambda: card(browser, "c9_outro", card_html(
                "Refleksiv portfolio", "E’tiboringiz uchun rahmat!",
                "Savollar bo‘lsa — administratorga murojaat qiling"), OUTRO, hold=1.2)),
        ]
        for key, fn in steps:
            if only and key not in only:
                continue
            t = time.time()
            res = await fn()
            dur = res["t_end"] - res["t_start"]
            speech = sum(json.loads(Path(a["path"]).with_suffix(".json").read_text(encoding="utf-8"))["dur"]
                         for a in res["audio"])
            print(f"{key:8s} {dur:6.1f}s  (nutq {speech:5.1f}s, {len(res['frames'])} kadr, {time.time() - t:5.1f}s)")
            results.append(res)
        await browser.close()
    return results


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    only = sys.argv[2:] or None
    if mode == "build":
        results = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    else:
        engine.DRY = mode == "dry"
        results = asyncio.run(record(only))
        if mode == "dry":
            print("dry: OK")
            return
        (BUILD / "timeline.json").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    total = sum(r["t_end"] - r["t_start"] for r in results)
    print(f"jami: {total:.1f}s ({total / 60:.2f} daqiqa)")
    OUT.mkdir(exist_ok=True)
    dur, n = build_video(results, OUT / "Refleksiv_portfolio_qollanma.mp4")
    print(f"video: {dur:.1f}s, {n} subtitr")


if __name__ == "__main__":
    main()
