from telethon import TelegramClient

# ======================
# TELEGRAM CREDENTIALS
# ======================
API_ID = 33281003
API_HASH = "3576c45f67b6223bbb4bf596b861bfb5"

SESSION_PATH = "sessions/main"

# ======================
# LOGIN
# ======================
with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
    print("✅ Telegram login successful")
    print("📁 Session saved at:", SESSION_PATH + ".session")
