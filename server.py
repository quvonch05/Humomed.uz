import os
import json
import asyncio
from aiohttp import web
import aiohttp_cors
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

# Telegram Bot tokeningizni yozing
BOT_TOKEN = "7283268717:AAH6F9JJdwJq54COIRZqraaX-vHR07tehEU" # O'zingizning haqiqiy tokeningizni qoldiring

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN and "..." not in BOT_TOKEN else None
dp = Dispatcher()

DATA_FILE = "humomed_db.json"

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

def load_db():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DB, f, ensure_ascii=False, indent=2)
        return DEFAULT_DB
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DB

def save_db(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================= TELEGRAM BOT LOGIKASI =================
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👨‍⚕️ <b>Humo Med — Shifokorlar Tizimi</b>\n\n"
        "Bemor tahlil natijasini saytga chiqarish uchun quyidagi formatda yuboring:\n"
        "<code>KOD | Bemor Ismi | Tahlil Turi | Vrach Ismi | Xulosa</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>HM-0077 | Sardor Aliyev | Biokimyo | Dr. Jasur | Natijalar me'yorda</code>\n\n"
        "📎 PDF yoki rasm yuborayotganda izoh (caption) qismiga shu formatda yozing!"
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
    if "|" not in raw_text:
        await message.reply("⚠️ Format noto‘g‘ri! Elementlarni <b>|</b> bilan ajrating.")
        return
    parts = [p.strip() for p in raw_text.split("|")]
    code = parts[0].upper()
    patient = parts[1] if len(parts) > 1 else "Bemor"
    test_type = parts[2] if len(parts) > 2 else "Umumiy tahlil"
    doctor = parts[3] if len(parts) > 3 else "Humo Med Shifokori"
    summary = parts[4] if len(parts) > 4 else "Tahlil natijalari tayyor."

    db = load_db()
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
    save_db(db)
    await message.reply(f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n🔑 Kod: <code>{code}</code>\n👤 Bemor: {patient}\n🌐 Saytda darhol ko‘rinadi!")

# ================= REST API HANDLERS =================
async def api_health(request):
    return web.Response(text="Humo Med API Live OK!")

async def api_get_full_db(request):
    return web.json_response(load_db())

async def api_get_lab_by_code(request):
    code = request.match_info.get('code', '').upper()
    db = load_db()
    if code in db.get("lab_results", {}):
        return web.json_response({"status": "success", "data": db["lab_results"][code]})
    return web.json_response({"status": "not_found"}, status=404)

async def api_update_section(request):
    sec = request.match_info.get('section', '')
    try:
        body = await request.json()
        db = load_db()
        db[sec] = body
        save_db(db)
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ================= ASOSIY RUNNER =================
async def start_server():
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*"
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
    print(f"🚀 API Server 0.0.0.0:{port} portida ishga tushdi")

    if bot:
        asyncio.create_task(dp.start_polling(bot))

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_server())
