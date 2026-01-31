import asyncio
from database import db

async def run_migration():
    await db.connect()
    # Add transcript_text column
    try:
        await db.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS transcript_text TEXT;")
        print("Successfully added transcript_text column to tickets table.")
    except Exception as e:
        print(f"Error executing migration: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
