from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from contextlib import asynccontextmanager
import asyncio
import os
import logging

# ======================
# CONFIG
# ======================
API_ID = 33281003
API_HASH = "3576c45f67b6223bbb4bf596b861bfb5"

BASE_DIR = "/home/ubuntu/telegram-number-check-python"
SESSION_DIR = f"{BASE_DIR}/sessions"
SESSION_NAME = f"{SESSION_DIR}/main"

MAX_BATCH = 10
BATCH_DELAY = 2

os.makedirs(SESSION_DIR, exist_ok=True)

# ======================
# LOGGING
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("telegram-checker")

# ======================
# FASTAPI + TELEGRAM
# ======================
client: TelegramClient | None = None
client_lock = asyncio.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session not authorized")

    log.info("Telegram client connected")
    yield
    await client.disconnect()
    log.info("Telegram client disconnected")

app = FastAPI(title="Telegram Number Checker", lifespan=lifespan)

# ======================
# REQUEST MODEL
# ======================
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]

# ======================
# FORMAT USER
# ======================
def format_user(user):
    return {
        "exists": True,
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "bot": user.bot,
        "verified": getattr(user, "verified", False),
        "premium": getattr(user, "premium", False),
    }

# ======================
# CORE CHECK (BATCHED)
# ======================
async def check_batch(numbers: list[str]) -> dict:
    results = {}

    contacts = [
        InputPhoneContact(
            client_id=i,
            phone=num,
            first_name="Temp",
            last_name="User"
        )
        for i, num in enumerate(numbers)
    ]

    try:
        log.info(f"Importing {len(numbers)} numbers")
        res = await client(ImportContactsRequest(contacts))

    except FloodWaitError as e:
        log.warning(f"FloodWait {e.seconds}s — sleeping")
        await asyncio.sleep(e.seconds)
        return await check_batch(numbers)

    except Exception as e:
        log.error(f"Import failed: {e}")
        for n in numbers:
            results[n] = {"exists": False, "error": "import_failed"}
        return results

    found = {u.phone: u for u in res.users}

    for num in numbers:
        if num in found:
            results[num] = format_user(found[num])
        else:
            results[num] = {"exists": False}

    # cleanup contacts
    try:
        await client(DeleteContactsRequest(res.users))
    except Exception:
        pass

    return results

# ======================
# API ENDPOINT
# ======================
@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):
    if not request.phone_numbers:
        raise HTTPException(400, "phone_numbers list is empty")

    numbers = request.phone_numbers[:30]
    results = {}

    async with client_lock:
        for i in range(0, len(numbers), MAX_BATCH):
            batch = numbers[i:i + MAX_BATCH]
            batch_result = await check_batch(batch)
            results.update(batch_result)
            await asyncio.sleep(BATCH_DELAY)

    return {
        "status": True,
        "total_checked": len(numbers),
        "data": results
    }
