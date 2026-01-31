import asyncio
from database import db

async def update():
    await db.connect()
    sql = """
    ALTER TABLE guild_config ADD COLUMN IF NOT EXISTS automod_invite_links BOOLEAN DEFAULT FALSE;
    """
    await db.execute(sql)
    await db.close()
    print("Database updated for Automod.")

if __name__ == "__main__":
    asyncio.run(update())
