import os
import asyncio
import re
from datetime import datetime
from aiohttp import web, ClientSession
import aiohttp_cors
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

# Sozlamalar
BOT_TOKEN = "7283268717:AAH6F9JJdwJq54COIRZqraaX-vHR07tehEU"
FIREBASE_URL = "https://humomed-a5f76-default-rtdb.firebaseio.com"

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# ================= FIREBASE'GA SAQLASH FUNKSIYASI =================
async def save_lab_to_firebase(code: str, payload: dict) -> bool:
    url = f"{FIREBASE_URL}/lab_results/{code}.json"
    try:
        async with ClientSession() as session:
            async with session.put(url, json=payload) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"⚠️ Firebase'ga yuborishda xatolik: {e}")
        return False

# ================= TELEGRAM BOT =================
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👨‍⚕️ <b>Humo Med — Shifokorlar Tizimi (Firebase 24/7)</b>\n\n"
        "Bemor tahlil natijasini saytga chiqarish uchun quyidagi formatda yuboring:\n"
        "<code>KOD | Bemor Ismi | Tahlil Turi | Vrach Ismi | Xulosa</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>HM-0077 | Sardor Aliyev | Biokimyo | Dr. Jasur | Natijalar me'yorda</code>",
        parse_mode="HTML"
    )

@dp.message(F.text)
async def handle_text_lab(message: types.Message):
    await parse_and_store(message.text, message)

@dp.message(F.document | F.photo)
async def handle_file_lab(message: types.Message):
    caption = message.caption
    if not caption:
        await message.reply(
            "⚠️ Fayl izohiga (caption) ma'lumotlarni yozing!\n"
            "Format: <code>HM-0077 | Ism | Tahlil | Vrach | Xulosa</code>",
            parse_mode="HTML"
        )
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

    lab_entry = {
        "id": int(datetime.now().timestamp() * 1000),
        "code": code,
        "patient": patient,
        "testType": test_type,
        "doctor": doctor,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary,
        "fileUrl": file_url
    }

    success = await save_lab_to_firebase(code, lab_entry)
    if success:
        await message.reply(
            f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n"
            f"🔑 Kod: <code>{code}</code>\n"
            f"👤 Bemor: {patient}\n"
            f"☁️ Baza: <b>Google Firebase (24/7)</b>",
            parse_mode="HTML"
        )
    else:
        await message.reply("❌ Firebase bazasiga saqlashda xatolik yuz berdi! Rules sozlamalarini tekshiring.")

# ================= RENDER VA UPTIMEROBOT UCHUN HEALTH CHECK =================
CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

async def api_health(request):
    return web.Response(text="Humo Med Bot & Firebase Live OK!", headers=CACHE_HEADERS)

# ================= SERVER VA BOTNI ISHGA TUSHIRISH =================
async def start_server():
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, 
            expose_headers="*", 
            allow_headers="*"
        )
    })

    cors.add(app.router.add_get('/', api_health))

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🚀 Server 0.0.0.0:{port} portida ishlamoqda")

    if bot:
        # Eski qotib qolgan webhook va sessiyalarni tozalash
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(dp.start_polling(bot))
        print("🤖 Telegram-bot muvaffaqiyatli ishga tushdi!")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_server())
