import asyncio
from database import db

async def check():
    await db.connect()
    # Check columns in guild_config
    sql = "SELECT column_name FROM information_schema.columns WHERE table_name = 'guild_config';"
    cols = await db.fetch(sql)
    print("Columns in guild_config:")
    for c in cols:
        print(f"- {c['column_name']}")
    
    # Check a specific record
    guilds = await db.fetch("SELECT guild_id, log_channel_id FROM guild_config;")
    print("\nGuild Configurations:")
    for g in guilds:
        print(f"Guild: {g['guild_id']} | Log Channel: {g['log_channel_id']}")
        
    await db.close()

if __name__ == "__main__":
    asyncio.run(check())
