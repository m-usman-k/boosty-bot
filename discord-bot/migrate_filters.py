import asyncio
from database import db

async def update():
    await db.connect()
    sql = """
    CREATE TABLE IF NOT EXISTS word_filters (
        id SERIAL PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        phrase TEXT NOT NULL,
        UNIQUE(guild_id, phrase)
    );
    """
    await db.execute(sql)
    await db.close()
    print("Database updated for Word Filtering.")

if __name__ == "__main__":
    asyncio.run(update())
