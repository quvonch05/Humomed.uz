import asyncio
import logging
import os
import aiohttp
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- SOZLAMALAR ---
# Quyidagi qatorga o'zingizning bot tokeningizni qo'ying
BOT_TOKEN = "7283268717:AAH6F9JJdwJq54COIRZqraaX-vHR07tehEU"
FIREBASE_URL = "https://humomed-a5f76-default-rtdb.firebaseio.com"

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# --- BUYRUQLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "🏥 <b>Humo Med — Shifokorlar Tizimi (Firebase 24/7)</b>\n\n"
        "Bemor tahlil natijasini saytga chiqarish uchun quyidagi formatda yuboring:\n"
        "<code>KOD | Bemor Ismi | Tahlil Turi | Vrach Ismi | Xulosa</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>HM-0077 | Sardor Aliyev | Biokimyo | Dr. Jasur | Natijalar me'yorda</code>\n\n"
        "📋 Qabulga yozilgan yangi bemorlar navbatini ko'rish uchun /navbatlar ni bosing."
    )
    await message.answer(text)

@dp.message(Command("navbatlar"))
async def cmd_navbatlar(message: types.Message):
    await message.answer("🔄 <i>Firebase bazasidan yangi navbatlar tekshirilmoqda...</i>")
    
    try:
        # requests o'rniga aiohttp asinxron kutubxonasidan foydalanamiz (bot qotib qolmasligi uchun)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{FIREBASE_URL}/bookings.json") as response:
                bookings = await response.json()
        
        if not bookings:
            await message.answer("✅ Hozircha hech qanday yangi navbat qabul qilinmagan.")
            return

        text = "🗓 <b>Bemorlar navbati (Saytdan yozilganlar):</b>\n\n"
        
        # Ro'yxat (list) yoki Lug'at (dict) ekanligini ajratib olamiz
        if isinstance(bookings, list):
            bookings_list = [b for b in bookings if b is not None]
        else:
            bookings_list = list(bookings.values())

        # Eng yangi navbatlar birinchi chiqishi uchun teskari tartiblaymiz
        bookings_list.sort(key=lambda x: x.get('id', 0), reverse=True)

        if not bookings_list:
            await message.answer("✅ Hozircha hech qanday yangi navbat qabul qilinmagan.")
            return

        # Ohirgi qo'shilganidan boshlab faqat 15 tasini ko'rsatamiz
        for idx, b in enumerate(bookings_list[:15], start=1):
            text += f"{idx}. <b>Bemor:</b> {b.get('name', 'Noma\'lum')}\n"
            text += f"📞 <b>Tel:</b> {b.get('phone', '-')}\n"
            text += f"🩺 <b>Xizmat:</b> {b.get('service', '-')} | <b>Shifokor:</b> {b.get('doctor', 'Umumiy qabul')}\n"
            text += f"⏰ <b>Vaqt:</b> {b.get('dateReadable', '-')}\n"
            text += f"—————————————\n"

        await message.answer(text)
        
    except Exception as e:
        await message.answer(f"❌ Navbatlarni tortishda xatolik yuz berdi:\n<code>{e}</code>")

@dp.message(F.text.contains("|"))
async def process_lab_result(message: types.Message):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 5:
            await message.answer("⚠️ Format noto'g'ri. 5 ta qism bo'lishi kerak:\n<code>KOD | Ism | Turi | Vrach | Xulosa</code>")
            return

        lab_code, patient, test_type, doctor, summary = parts
        lab_code = lab_code.upper().replace(" ", "")

        data_to_save = {
            "id": int(datetime.now().timestamp()),
            "code": lab_code,
            "patient": patient,
            "testType": test_type,
            "doctor": doctor,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": summary,
            "fileUrl": ""
        }

        # Tahlil natijalarini ham asinxron tarzda saqlaymiz
        async with aiohttp.ClientSession() as session:
            async with session.put(f"{FIREBASE_URL}/lab_results/{lab_code}.json", json=data_to_save) as response:
                if response.status == 200:
                    await message.answer(f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n\n🆔 Kod: <b>{lab_code}</b>\nBemor saytdan shu kod orqali natijasini o'qishi mumkin.")
                else:
                    await message.answer(f"❌ Firebase bazasiga saqlashda xatolik yuz berdi! HTTP {response.status}\nRules sozlamalarini tekshiring.")

    except Exception as e:
        await message.answer(f"⚠️ Xatolik yuz berdi: {e}")

# --- RAILWAY UCHUN SERVER SOZLAMALARI ---
async def handle_ping(request):
    return web.Response(text="Humo Med Bot va Server 24/7 ishlamoqda!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway beradigan port yoki standart 10000 port
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"🚀 Server 0.0.0.0:{port} portida ishlamoqda")
    
    # Botni webhookdan tozalab, polling usulida ishga tushirish
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Telegram-bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_server())
        
