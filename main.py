from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
import asyncio

app = FastAPI()

# Model for request
class PhoneNumberRequest(BaseModel):
    phone_numbers: list[str]
    app_id: int
    api_hash: str
    session_name: str = "session"  # optional

# Async function to check a number
async def check_number(client: TelegramClient, number: str):
    try:
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
            }
        }
    except Exception as e:
        return {number: {"error": str(e)}}

@app.post("/check")
async def check_numbers(request: PhoneNumberRequest):
    client = TelegramClient(request.session_name, request.app_id, request.api_hash)
    await client.start()
    
    temp_contacts = []
    # Step 1: Prepare temporary contacts
    for i, number in enumerate(request.phone_numbers):
        temp_contacts.append(
            InputPhoneContact(client_id=i, phone=number, first_name="Temp", last_name="User")
        )

    # Step 2: Import temporary contacts
    if temp_contacts:
        await client(ImportContactsRequest(temp_contacts))

    # Step 3: Check each number
    results_list = await asyncio.gather(
        *(check_number(client, number) for number in request.phone_numbers)
    )

    # Step 4: Remove temporary contacts
    if temp_contacts:
        await client(DeleteContactsRequest([await client.get_entity(number) for number in request.phone_numbers]))

    await client.disconnect()

    # Merge result
    results = {}
    for r in results_list:
        results.update(r)
    
    return results
