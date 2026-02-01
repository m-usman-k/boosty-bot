import os
import httpx
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_API_URL = "https://discord.com/api/v10"

async def get_access_token(code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{DISCORD_API_URL}/oauth2/token", data=data, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get access token")
        return response.json()

async def get_user_info(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get user info")
        return response.json()

async def get_user_guilds(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me/guilds", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to get user guilds")
        return response.json()
async def get_bot_guilds():
    bot_token = os.getenv("DISCORD_TOKEN")
    headers = {"Authorization": f"Bot {bot_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/users/@me/guilds", headers=headers)
        if response.status_code != 200:
            return []
        return response.json()

async def get_guild_channels(guild_id: int):
    bot_token = os.getenv("DISCORD_TOKEN")
    headers = {"Authorization": f"Bot {bot_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/guilds/{guild_id}/channels", headers=headers)
        if response.status_code != 200:
            return []
        return response.json()

async def get_guild_roles(guild_id: int):
    bot_token = os.getenv("DISCORD_TOKEN")
    headers = {"Authorization": f"Bot {bot_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DISCORD_API_URL}/guilds/{guild_id}/roles", headers=headers)
        if response.status_code != 200:
            return []
        return response.json()
