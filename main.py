from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import os
import uuid

app = FastAPI(title="Telegram Number Checker")

BASE_DIR = "/home/ubuntu/telegram-number-check-python"
SESSION_DIR = f"{BASE_DIR}/sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# ======================
# REQUEST MODEL
# ======================
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]
    app_id: int
    api_hash: str

# ======================
# HELPERS
# ======================
def format_user(user, temp: bool):
    return {
        "exists": True,
        "id": user.id,
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "phone": getattr(user, "phone", None),
        "bot": getattr(user, "bot", False),
        "verified": getattr(user, "verified", False),
        "premium": getattr(user, "premium", False),
        "temp": temp
    }

# ======================
# CHECK NUMBER
# ======================
async def check_number(client: TelegramClient, number: str):
    try:
        user = await client.get_entity(number)
        return {number: format_user(user, temp=False)}

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

        except Exception as e:
            return {number: {"exists": False, "error": str(e)}}

    except Exception as e:
        return {number: {"exists": False, "error": str(e)}}

# ======================
# API
# ======================
@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):

    session_name = f"{SESSION_DIR}/{uuid.uuid4()}"
    client = TelegramClient(session_name, request.app_id, request.api_hash)

    try:
        await client.start()
    except SessionPasswordNeededError:
        raise HTTPException(401, "Two-factor authentication enabled")
    except Exception as e:
        raise HTTPException(500, f"Telegram start failed: {str(e)}")

    results_list = await asyncio.gather(
        *(check_number(client, n) for n in request.phone_numbers)
    )

    await client.disconnect()

    # 🧹 cleanup session files
    try:
        for f in os.listdir(SESSION_DIR):
            if session_name.split("/")[-1] in f:
                os.remove(f"{SESSION_DIR}/{f}")
    except Exception:
        pass

    results = {}
    for r in results_list:
        results.update(r)

    return results
