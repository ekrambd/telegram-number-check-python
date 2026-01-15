from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import os

app = FastAPI(title="Telegram Number Checker")

BASE_DIR = "/home/ubuntu/telegram-number-check-python"
SESSION_DIR = f"{BASE_DIR}/sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# ======================
# REQUEST MODEL
# ======================
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]

# ======================
# FORMAT USER
# ======================
def format_user(user, temp=False):
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
        "temp": temp
    }

# ======================
# CHECK NUMBER
# ======================
async def check_number(client, number):
    try:
        user = await client.get_entity(number)
        return {number: format_user(user)}

    except ValueError:
        try:
            contact = InputPhoneContact(
                client_id=0,
                phone=number,
                first_name="Temp",
                last_name="User"
            )

            await client(ImportContactsRequest([contact]))
            user = await client.get_entity(number)

            try:
                await client(DeleteContactsRequest([user]))
            except Exception:
                pass

            return {number: format_user(user, temp=True)}

        except Exception:
            return {number: {"exists": False}}

    except Exception:
        return {number: {"exists": False}}

# ======================
# API
# ======================
@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):

    client = TelegramClient(
        "sessions/main",
        33281003,
        "3576c45f67b6223bbb4bf596b861bfb5"
    )

    try:
        await client.start()
    except SessionPasswordNeededError:
        raise HTTPException(401, "2FA enabled")
    except Exception as e:
        raise HTTPException(500, str(e))

    results_list = await asyncio.gather(
        *(check_number(client, n) for n in request.phone_numbers)
    )

    await client.disconnect()

    result = {}
    for r in results_list:
        result.update(r)

    return result
