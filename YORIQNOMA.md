# 📖 Telegram Bot — To'liq Yo'riqnoma

## 📁 Loyiha fayllari

```
telegram_bot/
├── bot.py           ← Asosiy bot kodi
├── database.py      ← Ma'lumotlar bazasi
├── requirements.txt ← Kerakli kutubxonalar
├── railway.toml     ← Railway sozlamalari
├── .env.example     ← Token namunasi
└── .gitignore       ← Git uchun
```

---

## 1-QADAM: Bot token olish

1. Telegramda **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini kiriting (masalan: `MyEduBot`)
4. Username kiriting (masalan: `myedu_bot`) — oxirida `_bot` bo'lishi shart
5. **TOKEN** ni oling va saqlang (masalan: `1234567890:ABCDEFghijk...`)

---

## 2-QADAM: O'zingizning Telegram ID ni bilish

1. Telegramda **@userinfobot** ga yozing
2. `/start` yuboring
3. **Id:** dagi raqamni saqlang (masalan: `987654321`)

---

## 3-QADAM: GitHub ga yuklash

1. **github.com** ga kiring
2. **New repository** bosing
3. Nom bering: `my-edu-bot`
4. **Private** tanlang (xavfsizlik uchun)
5. **Create repository** bosing

Keyin kompyuteringizda (Terminal / CMD):
```bash
cd telegram_bot
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/SIZNING_USERNAME/my-edu-bot.git
git push -u origin main
```

---

## 4-QADAM: Railway ga deploy qilish (TEKIN)

1. **railway.app** ga kiring
2. GitHub akkount bilan kiring
3. **New Project** → **Deploy from GitHub repo**
4. Yaratgan repo ni tanlang
5. **Variables** bo'limiga o'ting va qo'shing:

| Kalit | Qiymat |
|-------|--------|
| `BOT_TOKEN` | BotFather dan olgan token |
| `ADMIN_ID` | Sizning Telegram ID raqamingiz |

6. **Deploy** bosing — 2-3 daqiqada ishlaydi! ✅

---

## 5-QADAM: Botni sinash

1. Telegramda botingizni toping
2. `/start` yuboring
3. Asosiy menyu ko'rinishi kerak

---

## 🔧 BOT ISHLATISH

### Admin sifatida content qo'shish:

**Test qo'shish:**
1. `/admin` → "Test qo'shish" bosing
2. Test nomini yozing
3. Savollarni quyidagi formatda yozing:
```
Qaysi yil O'zbekiston mustaqillikka erishdi?
A) 1990
B) 1991
C) 1992
D) 1993
To'g'ri javob: B
```
4. Barcha savollarni kiritib `/done` bosing

**Qo'llanma qo'shish:**
1. `/admin` → "Qo'llanma qo'shish"
2. Sarlavha yozing
3. Matn yozing

**Video qo'shish:**
1. `/admin` → "Video qo'shish"
2. Sarlavha, tavsif, YouTube/Telegram havolasini yozing

### Foydalanuvchini tasdiqlash:
- Kimdir `/start` bosib so'rov yuborsa, sizga xabar keladi
- **✅ Tasdiqlash** bosing — u botdan foydalana oladi
- **❌ Rad etish** bosing — foydalana olmaydi

---

## 📊 Bot imkoniyatlari

| Xususiyat | Tavsif |
|-----------|--------|
| 🔐 Ruxsat tizimi | Faqat tasdiqlangan foydalanuvchilar |
| 📝 Testlar | 4 variantli, avtomatik tekshirish |
| 📊 Natijalar | Foiz va ball ko'rsatiladi |
| 📚 Qo'llanmalar | Matn ko'rinishida |
| 🎬 Video darslar | Havolalar |
| 👥 Admin panel | Foydalanuvchilar, statistika |

---

## ❓ Muammolar

**Bot ishlamayapti?**
→ Railway → Logs bo'limini tekshiring

**Token xato?**
→ `.env` dagi `BOT_TOKEN` ni tekshiring

**Admin panel ko'rinmayapti?**
→ `ADMIN_ID` to'g'ri kiritilganini tekshiring

---

## 💡 Maslahat

- Har doim `.env` faylini GitHub ga yuklamang (`.gitignore` da yozilgan)
- Railway bepul 500 soat/oy beradi — bu yetarli
- Bot bazasi Railway serverida saqlanadi

---

*Savollar bo'lsa — kod ichidagi izohlarni o'qing!*
