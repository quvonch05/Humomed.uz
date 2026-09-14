import os
import json
import asyncio
import re
from aiohttp import web
import aiohttp_cors
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
import asyncpg

BOT_TOKEN = "7283268717:AAH6F9JJdwJq54COIRZqraaX-vHR07tehEU"
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()
db_pool = None

DEFAULT_DB = {
    "services": [
        {"id": 1, "name": "MRT / MSKT", "desc": "1.5 Tesla yuqori aniqlikdagi diagnostika", "price": "380,000 so‘m", "image": ""},
        {"id": 2, "name": "Kardiologiya", "desc": "EKG, EXO-KG va qon bosimi nazorati", "price": "150,000 so‘m", "image": ""},
        {"id": 3, "name": "Laboratoriya", "desc": "150+ turdagi tahlillar tezkor natijasi", "price": "80,000 so‘mdan", "image": ""}
    ],
    "doctors": [
        {"id": 1, "name": "Dr. Jasur Aliyev", "specialty": "Kardiolog (Oliy toifa)", "exp": "14 yil"},
        {"id": 2, "name": "Dr. Nilufar M.", "specialty": "Bosh Nevropatolog", "exp": "10 yil"},
        {"id": 3, "name": "Dr. Sanjar Karimov", "specialty": "MRT / Rentgenolog", "exp": "8 yil"}
    ],
    "bookings": [],
    "lab_results": {
        "HM-0077": {
            "id": 1,
            "code": "HM-0077",
            "patient": "Quvonchbek Baratov",
            "testType": "Biokimyo va Umumiy Qon Tahlili",
            "doctor": "Dr. Jasur Aliyev",
            "date": "2026-09-14",
            "summary": "Barcha ko'rsatkichlar me'yorda. Gemoglobin: 145 g/l.",
            "fileUrl": ""
        }
    }
}

# ================= POSTGRESQL FUNKSIYALARI =================
async def init_db():
    global db_pool
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL topilmadi, mahalliy rejimda ishlaydi.")
        return

    # Render URL'dagi postgres:// ni postgresql:// ga o'tkazish
    pg_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    db_pool = await asyncpg.create_pool(pg_url)

    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS portal_store (
                id INT PRIMARY KEY,
                data JSONB NOT NULL
            );
        ''')
        row = await conn.fetchrow('SELECT data FROM portal_store WHERE id = 1;')
        if not row:
            await conn.execute(
                'INSERT INTO portal_store (id, data) VALUES (1, $1);',
                json.dumps(DEFAULT_DB)
            )
            print("✅ PostgreSQL: Dastlabki ma'lumotlar bazaga kiritildi.")

async def get_db_data():
    if db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow('SELECT data FROM portal_store WHERE id = 1;')
            if row:
                data = row['data']
                return json.loads(data) if isinstance(data, str) else data
    return DEFAULT_DB

async def save_db_data(data):
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE portal_store SET data = $1 WHERE id = 1;',
                json.dumps(data)
            )

# ================= TELEGRAM BOT =================
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👨‍⚕️ <b>Humo Med — Shifokorlar Tizimi</b>\n\n"
        "Bemor tahlil natijasini saytga chiqarish uchun quyidagi formatda yuboring:\n"
        "<code>KOD | Bemor Ismi | Tahlil Turi | Vrach Ismi | Xulosa</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>HM-0077 | Sardor Aliyev | Biokimyo | Dr. Jasur | Natijalar me'yorda</code>"
    )

@dp.message(F.text)
async def handle_text_lab(message: types.Message):
    await parse_and_store(message.text, message)

@dp.message(F.document | F.photo)
async def handle_file_lab(message: types.Message):
    caption = message.caption
    if not caption:
        await message.reply("⚠️ Fayl izohiga (caption) ma'lumotlarni yozing!\nFormat: <code>HM-0077 | Ism | Tahlil | Vrach | Xulosa</code>")
        return
    file_id = message.document.file_id if message.document else message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    await parse_and_store(caption, message, file_url=file_url)

async def parse_and_store(raw_text: str, message: types.Message, file_url=""):
    clean_text = re.sub(r'<[^>]*>', '', raw_text).strip()
    if "|" not in clean_text:
        await message.reply("⚠️ Format noto‘g‘ri! Elementlarni | bilan ajrating.")
        return
    
    parts = [p.strip() for p in clean_text.split("|")]
    code = parts[0].replace(" ", "").upper()
    patient = parts[1] if len(parts) > 1 else "Bemor"
    test_type = parts[2] if len(parts) > 2 else "Umumiy tahlil"
    doctor = parts[3] if len(parts) > 3 else "Humo Med Shifokori"
    summary = parts[4] if len(parts) > 4 else "Tahlil natijalari tayyor."

    db = await get_db_data()
    if "lab_results" not in db or not isinstance(db["lab_results"], dict):
        db["lab_results"] = {}

    db["lab_results"][code] = {
        "id": int(asyncio.get_event_loop().time() * 1000),
        "code": code,
        "patient": patient,
        "testType": test_type,
        "doctor": doctor,
        "date": "2026-09-14",
        "summary": summary,
        "fileUrl": file_url
    }
    await save_db_data(db)
    await message.reply(
        f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n"
        f"🔑 Kod: <code>{code}</code>\n"
        f"👤 Bemor: {patient}\n"
        f"🌐 Baza doimiy PostgreSQL xotirasiga yozildi!"
    )

# ================= REST API =================
CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

async def api_health(request):
    return web.Response(text="Humo Med PostgreSQL Live OK!", headers=CACHE_HEADERS)

async def api_get_full_db(request):
    db = await get_db_data()
    return web.json_response(db, headers=CACHE_HEADERS)

async def api_get_lab_by_code(request):
    raw_code = request.match_info.get('code', '')
    clean_code = raw_code.replace(" ", "").replace("%20", "").upper()
    
    db = await get_db_data()
    labs = db.get("lab_results", {})

    if isinstance(labs, dict) and clean_code in labs:
        return web.json_response({"status": "success", "data": labs[clean_code]}, headers=CACHE_HEADERS)

    for k, item in (labs.items() if isinstance(labs, dict) else enumerate(labs)):
        if isinstance(item, dict):
            item_code = item.get("code", "").replace(" ", "").upper()
            if item_code == clean_code:
                return web.json_response({"status": "success", "data": item}, headers=CACHE_HEADERS)

    return web.json_response({"status": "not_found", "message": "Tahlil topilmadi"}, status=404, headers=CACHE_HEADERS)

async def api_update_section(request):
    sec = request.match_info.get('section', '')
    try:
        body = await request.json()
        db = await get_db_data()
        db[sec] = body
        await save_db_data(db)
        return web.json_response({"status": "success"}, headers=CACHE_HEADERS)
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500, headers=CACHE_HEADERS)

# ================= SERVER START =================
async def start_server():
    await init_db()

    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, 
            expose_headers="*", 
            allow_headers="*"
        )
    })

    cors.add(app.router.add_get('/', api_health))
    cors.add(app.router.add_get('/api/db', api_get_full_db))
    cors.add(app.router.add_get('/api/results/{code}', api_get_lab_by_code))
    cors.add(app.router.add_post('/api/update/{section}', api_update_section))

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🚀 Server 0.0.0.0:{port} portida ishlamoqda")

    if bot:
        asyncio.create_task(dp.start_polling(bot))

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_server())
