from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import os

app = FastAPI(title="Telegram Number Checker")

# ======================
# DIRECTORIES
# ======================
BASE_DIR = "/home/ubuntu/telegram-number-check-python"
SESSION_DIR = f"{BASE_DIR}/sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Use a permanent session (must login manually once)
PERMANENT_SESSION = f"{SESSION_DIR}/main"

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
        # Check if number exists in Telegram
        user = await client.get_entity(number)
        return {number: format_user(user, temp=False)}

    except ValueError:
        # Not in contacts, create temp contact
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
# API ENDPOINT
# ======================
@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):

    # Use permanent session
    client = TelegramClient(PERMANENT_SESSION, request.app_id, request.api_hash)

    try:
        await client.start()  # No interactive input required
    except SessionPasswordNeededError:
        raise HTTPException(401, "Two-factor authentication enabled for this account")
    except Exception as e:
        raise HTTPException(500, f"Telegram start failed: {str(e)}")

    # Check all numbers concurrently
    results_list = await asyncio.gather(
        *(check_number(client, n) for n in request.phone_numbers)
    )

    await client.disconnect()

    # Merge results
    results = {}
    for r in results_list:
        results.update(r)

    return results
