import asyncio
from database import db

async def check():
    await db.connect()
    # Check all columns in guild_config
    sql = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'guild_config' ORDER BY column_name;"
    cols = await db.fetch(sql)
    print("Full Columns in guild_config:")
    for c in cols:
        print(f"- {c['column_name']} ({c['data_type']})")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(check())
