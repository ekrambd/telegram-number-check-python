from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import os

# =========================
# APP CONFIG
# =========================
app = FastAPI(title="Telegram Number Checker")

BASE_DIR = "/home/ubuntu/telegram-number-check-python"
SESSION_DIR = f"{BASE_DIR}/sessions"

# Ensure session directory exists & writable
os.makedirs(SESSION_DIR, exist_ok=True)

# =========================
# REQUEST MODEL
# =========================
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]
    app_id: int
    api_hash: str
    session_name: str = "default"

# =========================
# CHECK SINGLE NUMBER
# =========================
async def check_number(client: TelegramClient, number: str):
    # 1️⃣ Try direct lookup (already in contacts / known)
    try:
        user = await client.get_entity(number)
        return {
            number: format_user(user, temp=False)
        }

    except ValueError:
        # 2️⃣ Not found → try temp contact import
        try:
            temp_contact = InputPhoneContact(
                client_id=0,
                phone=number,
                first_name="Temp",
                last_name="User"
            )

            await client(ImportContactsRequest([temp_contact]))

            user = await client.get_entity(number)

            # cleanup
            try:
                await client(DeleteContactsRequest([user]))
            except Exception:
                pass

            return {
                number: format_user(user, temp=True)
            }

        except Exception as e:
            return {
                number: {
                    "exists": False,
                    "error": str(e),
                    "temp": True
                }
            }

    except Exception as e:
        return {
            number: {
                "exists": False,
                "error": str(e),
                "temp": False
            }
        }

# =========================
# FORMAT USER RESPONSE
# =========================
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

# =========================
# API ENDPOINT
# =========================
@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):

    session_path = f"{SESSION_DIR}/{request.session_name}"

    client = TelegramClient(
        session_path,
        request.app_id,
        request.api_hash
    )

    # Start client safely
    try:
        await client.start()
    except SessionPasswordNeededError:
        raise HTTPException(
            status_code=401,
            detail="Two-factor authentication enabled. Login required."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram client start failed: {str(e)}"
        )

    # Run all checks concurrently
    results_list = await asyncio.gather(
        *(check_number(client, num) for num in request.phone_numbers)
    )

    await client.disconnect()

    # Merge results
    results = {}
    for r in results_list:
        results.update(r)

    return results
