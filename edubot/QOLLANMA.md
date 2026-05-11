# 🚀 BOT ISHGA TUSHIRISH — BOSQICHMA-BOSQICH

Hech qanday kod yozmasdan, faqat bosish bilan!

---

## ✅ 1-QADAM — Bot token olish (5 daqiqa)

1. Telegramni oching
2. Qidiruv qatoriga yozing: **@BotFather**
3. Unga `/start` yuboring
4. Keyin `/newbot` yuboring
5. Bot nomini so'raydi → yozing masalan: `Mening Darslarim`
6. Username so'raydi → yozing masalan: `mening_darslar_bot`
   _(oxirida albatta `_bot` bo'lishi kerak)_
7. **BotFather sizga token beradi** — quyidagicha ko'rinadi:
   ```
   1234567890:ABCDEFGhijklmnopqrstuvwxyz123456
   ```
8. Bu tokenni **NUSXALAB OLING** (uni hech kimga bermang!)

---

## ✅ 2-QADAM — Telegram ID raqamingizni bilish (1 daqiqa)

1. Telegramda qidiruv: **@userinfobot**
2. `/start` yuboring
3. U sizga **Id:** degan raqam ko'rsatadi
4. Masalan: `987654321` — uni yozib oling

---

## ✅ 3-QADAM — GitHub ga yuklash (10 daqiqa)

### GitHub da yangi papka ochish:
1. **github.com** ga kiring (akkountingizga kiring)
2. Yuqori o'ngda **+** tugmasini bosing → **New repository**
3. Repository name: `edu-bot` deb yozing
4. **Private** ni tanlang ✅
5. **Create repository** tugmasini bosing

### Fayllarni yuklash:
1. Ochilgan sahifada **uploading an existing file** havolasini bosing
2. Yuklab olgan ZIP papkasidagi **barcha fayllarni** suring yoki tanlang:
   - `bot.py`
   - `database.py`
   - `requirements.txt`
   - `railway.toml`
   - `.env.example`
   - `.gitignore`
   - `BOTNI_ISHGA_TUSHIR.bat`
3. Pastda **Commit changes** tugmasini bosing

---

## ✅ 4-QADAM — Railway da ishga tushirish (10 daqiqa)

_(Railway — bepul server, botingiz 24/7 ishlaydi)_

1. **railway.app** ga kiring
2. **Login with GitHub** bosing
3. **New Project** tugmasini bosing
4. **Deploy from GitHub repo** tanlang
5. `edu-bot` reponi tanlang
6. Loyiha ochilgandan so'ng **Variables** bo'limiga o'ting
7. Quyidagilarni qo'shing:

   | Kalit nomi | Qiymati |
   |------------|---------|
   | `BOT_TOKEN` | BotFather dan olgan token |
   | `ADMIN_ID` | Sizning ID raqamingiz |

8. **Deploy** tugmasini bosing
9. 2-3 daqiqa kuting — **✅ Active** ko'rinsa, bot ishlayapti!

---

## ✅ 5-QADAM — Botni sinash

1. Telegramda **@sizning_bot_username** ga kiring
2. `/start` bosing
3. Asosiy menyu ko'rinadi — hammasi tayyor! 🎉

---

## 🔧 BOT ISHLATISH

### Admin sifatida test qo'shish:
1. `/admin` buyrug'ini yuboring
2. **"📝 Test qo'shish"** tugmasini bosing
3. Test nomini yozing, masalan: `Ona tili testi`
4. Har bir savolni shu formatda yozing:

```
Qaysi so'z to'g'ri yozilgan?
A) kitob
B) qitob
C) kittob
D) kytob
To'g'ri javob: A
```

5. Barcha savollarni kiritib `/done` yuboring ✅

### Foydalanuvchiga ruxsat berish:
- Kimdir botingizga `/start` bosib so'rov yuborsa
- Sizga **xabar keladi** ✅ Tasdiqlash yoki ❌ Rad etish tugmalari bilan
- **✅ Tasdiqlash** bossangiz — u botdan foydalana oladi

---

## ❓ Tez-tez so'raladigan savollar

**Bot ishlamayapti?**
→ Railway saytiga kiring → Loyihangiz → **Logs** — xato xabarni o'qing

**"Ruxsat yo'q" deyapti?**
→ Railway → Variables → `ADMIN_ID` to'g'ri kiritilganini tekshiring

**Token xato deyapti?**
→ Railway → Variables → `BOT_TOKEN` ni qayta kiriting (probel bo'lmasin)

---

## 📞 Yordam kerakmi?

Har qanday savolni menga yuboring — har bir qadamda yordam beraman!
