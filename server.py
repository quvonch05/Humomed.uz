import os
import json
import asyncio
from aiohttp import web
import aiohttp_cors
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

# Telegram botingiz tokeni
BOT_TOKEN = "7283268717:AAH6F9JJdwJq54COIRZqraaX-vHR07tehEU"

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN and "misol" not in BOT_TOKEN else None
dp = Dispatcher()

DATA_FILE = "lab_results.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        initial = {
            "HM-0077": {
                "code": "HM-0077",
                "patient": "Quvonchbek Baratov",
                "testType": "Biokimyo va Umumiy Qon Tahlili",
                "doctor": "Dr. Jasur Aliyev",
                "date": "2026-09-14",
                "summary": "Barcha ko'rsatkichlar me'yorda. Gemoglobin: 145 g/l.",
                "fileUrl": ""
            }
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False, indent=2)
        return initial
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
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
        "📎 PDF yoki Rasm fayl bo‘lsa, uni yuborishda izoh (caption) qismiga shu formatda yozing."
    )

@dp.message(F.text)
async def handle_text_lab(message: types.Message):
    await parse_and_store(message.text, message)

@dp.message(F.document | F.photo)
async def handle_file_lab(message: types.Message):
    caption = message.caption
    if not caption:
        await message.reply("⚠️ Iltimos, fayl bilan birga izoh (caption) qismida ma'lumotlarni yozing!\nFormat: <code>HM-0077 | Ism | Tahlil | Vrach | Xulosa</code>")
        return
    
    file_id = message.document.file_id if message.document else message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    await parse_and_store(caption, message, file_url=file_url)

async def parse_and_store(raw_text: str, message: types.Message, file_url=""):
    if "|" not in raw_text:
        await message.reply("⚠️ Format noto‘g‘ri! Elementlarni <b>|</b> bilan ajrating:\n<code>HM-0077 | Ism | Turi | Vrach | Xulosa</code>")
        return
    
    parts = [p.strip() for p in raw_text.split("|")]
    code = parts[0].upper()
    patient = parts[1] if len(parts) > 1 else "Bemor"
    test_type = parts[2] if len(parts) > 2 else "Umumiy tahlil"
    doctor = parts[3] if len(parts) > 3 else "Humo Med Shifokori"
    summary = parts[4] if len(parts) > 4 else "Tahlil natijalari tayyor."

    db = load_data()
    db[code] = {
        "code": code,
        "patient": patient,
        "testType": test_type,
        "doctor": doctor,
        "date": "2026-09-14",
        "summary": summary,
        "fileUrl": file_url
    }
    save_data(db)

    await message.reply(
        f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n"
        f"🔑 Kod: <code>{code}</code>\n"
        f"👤 Bemor: {patient}\n"
        f"🌐 Barcha qurilmalarda saytdan tekshirish mumkin!"
    )

# ================= REST API HANDLERS =================
async def api_health(request):
    return web.Response(text="Humo Med API is working successfully!")

async def api_get_all(request):
    data = load_data()
    return web.json_response(list(data.values()))

async def api_get_by_code(request):
    code = request.match_info.get('code', '').upper()
    data = load_data()
    if code in data:
        return web.json_response({"status": "success", "data": data[code]})
    return web.json_response({"status": "not_found", "message": "Tahlil topilmadi"}, status=404)

async def api_save_lab(request):
    try:
        body = await request.json()
        code = body.get("code", "").strip().upper()
        if not code:
            return web.json_response({"status": "error", "message": "Kod kiritilmagan"}, status=400)
        
        db = load_data()
        db[code] = {
            "code": code,
            "patient": body.get("patient", "Bemor"),
            "testType": body.get("testType", "Tahlil"),
            "doctor": body.get("doctor", "Shifokor"),
            "date": body.get("date", "2026-09-14"),
            "summary": body.get("summary", "Natijalar tayyor."),
            "fileUrl": body.get("fileUrl", "")
        }
        save_data(db)
        return web.json_response({"status": "success", "message": "Baza yangilandi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def api_delete_lab(request):
    code = request.match_info.get('code', '').upper()
    db = load_data()
    if code in db:
        del db[code]
        save_data(db)
        return web.json_response({"status": "success", "message": f"{code} o'chirildi"})
    return web.json_response({"status": "not_found", "message": "Topilmadi"}, status=404)

# ================= ASOSIY ISHGA TUSHIRISH =================
async def start_server():
    app = web.Application()
    
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    cors.add(app.router.add_get('/', api_health))
    cors.add(app.router.add_get('/api/results', api_get_all))
    cors.add(app.router.add_post('/api/results', api_save_lab))
    cors.add(app.router.add_get('/api/results/{code}', api_get_by_code))
    cors.add(app.router.add_delete('/api/results/{code}', api_delete_lab))

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🚀 Web Server ishga tushdi: 0.0.0.0:{port}")

    if bot:
        print("🤖 Telegram Bot polling boshlandi...")
        asyncio.create_task(dp.start_polling(bot))
    else:
        print("⚠️ Bot token ko'rsatilmagan yoki noto'g'ri, faqat Web Server ishlamoqda.")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_server())
