from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio

app = FastAPI(title="Telegram Number Checker")

# Request model
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]
    app_id: int
    api_hash: str
    session_name: str = "session"  # optional

# Async function to check a single number
async def check_number(client: TelegramClient, number: str):
    try:
        # Try to get entity directly (existing contacts)
        user = await client.get_entity(number)
        return {
            number: {
                "id": user.id,
                "username": getattr(user, "username", None),
                "first_name": getattr(user, "first_name", None),
                "last_name": getattr(user, "last_name", None),
                "phone": getattr(user, "phone", None),
                "bot": getattr(user, "bot", False),
                "verified": getattr(user, "verified", False),
                "premium": getattr(user, "premium", False),
                "temp": False,  # real contact
            }
        }
    except ValueError:
        # If not found, create a temporary contact
        temp_contact = InputPhoneContact(client_id=0, phone=number, first_name="Temp", last_name="User")
        try:
            await client(ImportContactsRequest([temp_contact]))
            user = await client.get_entity(number)
            await client(DeleteContactsRequest([user]))
            return {
                number: {
                    "id": user.id,
                    "username": getattr(user, "username", None),
                    "first_name": getattr(user, "first_name", None),
                    "last_name": getattr(user, "last_name", None),
                    "phone": getattr(user, "phone", None),
                    "bot": getattr(user, "bot", False),
                    "verified": getattr(user, "verified", False),
                    "premium": getattr(user, "premium", False),
                    "temp": True,  # temporary contact
                }
            }
        except Exception as e:
            return {number: {"error": str(e), "temp": True}}
    except Exception as e:
        return {number: {"error": str(e), "temp": False}}

@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):
    client = TelegramClient(request.session_name, request.app_id, request.api_hash)
    
    try:
        await client.start()
    except SessionPasswordNeededError:
        raise HTTPException(status_code=401, detail="Two-factor authentication required for this session.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start client: {str(e)}")

    # Run all numbers concurrently
    results_list = await asyncio.gather(
        *(check_number(client, number) for number in request.phone_numbers)
    )

    # Merge results
    results = {}
    for r in results_list:
        results.update(r)

    await client.disconnect()
    return results
