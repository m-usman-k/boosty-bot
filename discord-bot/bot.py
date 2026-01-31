import discord
from discord.ext import commands
import os
import logging
from config import Config
from database import db

# Setup Logging
logging.basicConfig(level=logging.INFO)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            help_command=None
        )

    async def setup_hook(self):
        # Connect to Database
        await db.connect()
        
        # Initialize Schema (Simple way for now, better to use migrations in production)
        with open('schema.sql', 'r') as f:
            schema = f.read()
            # Split commands by semicolon to execute one by one if needed, 
            # or execute block if supported. asyncpg execute supports multiple statements usually.
            await db.execute(schema)
            
        # Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                logging.info(f'Loaded Cog: {filename}')
        
        # Sync Commands
        await self.tree.sync()
        logging.info("Commands synced.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    async def close(self):
        await db.close()
        await super().close()

bot = MyBot()

if __name__ == "__main__":
    if not Config.TOKEN:
        logging.error("No token found. Please set DISCORD_TOKEN in .env")
    else:
        bot.run(Config.TOKEN)
