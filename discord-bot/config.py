import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TOKEN = os.getenv("DISCORD_TOKEN")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "discordbot")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    
    TRANSCRIPT_PATH = os.getenv("TRANSCRIPT_PATH", "./transcripts")
    
    # Colors
    COLOR_SUCCESS = int(os.getenv("COLOR_SUCCESS", "0x2ECC71"), 16)
    COLOR_ERROR = int(os.getenv("COLOR_ERROR", "0xE74C3C"), 16)
    COLOR_NEUTRAL = int(os.getenv("COLOR_NEUTRAL", "0x5865F2"), 16)
    
    # Common IDs (can be moved to DB or stayed here if static)
    # GUILD_ID = ... 
