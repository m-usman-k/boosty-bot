from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import oauth
from database import get_db
from models import GuildConfig, WordFilter, TicketReason, Ticket
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
# Better session config for local dev (handling localhost/127.0.0.1 better)
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET", "supersecretkey"),
    same_site="lax",
    https_only=False
)

# Create partial folders if not exists
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login")
async def login():
    encoded_uri = urllib.parse.quote(oauth.REDIRECT_URI, safe='')
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={oauth.CLIENT_ID}"
        f"&redirect_uri={encoded_uri}&response_type=code&scope=identify%20guilds"
    )
    return RedirectResponse(discord_auth_url)

@app.get("/callback")
async def callback(request: Request, code: str):
    token_resp = await oauth.get_access_token(code)
    access_token = token_resp["access_token"]
    user_info = await oauth.get_user_info(access_token)
    guilds = await oauth.get_user_guilds(access_token)
    bot_guilds = await oauth.get_bot_guilds()
    bot_guild_ids = [g["id"] for g in bot_guilds]
    
    # Store ONLY minimal user info (Avoid large data in cookies)
    request.session["user"] = {
        "id": user_info["id"],
        "username": user_info["username"],
        "avatar": user_info.get("avatar")
    }
    
    # Store ONLY minimal guild info
    admin_guilds = []
    for g in guilds:
        # User is admin (0x8) AND bot is in the guild
        is_admin = (int(g.get("permissions", 0)) & 0x8) == 0x8
        if is_admin and (str(g["id"]) in bot_guild_ids):
            admin_guilds.append({
                "id": g["id"],
                "name": g["name"],
                "icon": g.get("icon")
            })
    
    request.session["admin_guilds"] = admin_guilds
    
    # Force absolute redirect to the same domain we hit
    target_url = str(request.url_for("dashboard"))
    return RedirectResponse(url=target_url, status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/")
    
    guilds = request.session.get("admin_guilds", [])
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "guilds": guilds})

@app.get("/guild/{guild_id}", response_class=HTMLResponse)
async def guild_settings(request: Request, guild_id: int, db: AsyncSession = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/")
    
    # Security check: is user admin of this guild?
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Get current config
    result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
    config = result.scalar_one_or_none()
    
    if not config:
        # Create default config if bot joined but table doesn't have it
        config = GuildConfig(guild_id=guild_id)
        db.add(config)
        await db.commit()
        await db.refresh(config)

    # Fetch real-time data from Discord
    all_channels = await oauth.get_guild_channels(guild_id)
    roles = await oauth.get_guild_roles(guild_id)
    
    # Filter channels by type
    text_channels = [c for c in all_channels if c['type'] == 0]
    voice_channels = [c for c in all_channels if c['type'] == 2]
    categories = [c for c in all_channels if c['type'] == 4]
    
    # Fetch word filters
    filter_result = await db.execute(select(WordFilter).where(WordFilter.guild_id == guild_id))
    word_filters = filter_result.scalars().all()
    
    # Fetch ticket reasons
    reason_result = await db.execute(select(TicketReason).where(TicketReason.guild_id == guild_id))
    ticket_reasons = reason_result.scalars().all()
    
    # Fetch recent transcripts (closed tickets with transcripts)
    transcripts_result = await db.execute(
        select(Ticket)
        .where(Ticket.guild_id == guild_id, Ticket.transcript_text.isnot(None))
        .order_by(Ticket.id.desc())
        .limit(20)
    )
    recent_transcripts = transcripts_result.scalars().all()

    return templates.TemplateResponse("guild.html", {
        "request": request, 
        "user": user, 
        "config": config, 
        "guild_id": guild_id,
        "text_channels": text_channels,
        "voice_channels": voice_channels,
        "categories": categories,
        "word_filters": word_filters,
        "ticket_reasons": ticket_reasons,
        "transcripts": recent_transcripts,
        "roles": [{"id": r["id"], "name": r["name"]} for r in roles if r["name"] != "@everyone"]
    })

@app.post("/guild/{guild_id}/update")
async def update_settings(
    request: Request, 
    guild_id: int,
    log_channel_id: str = Form(None),
    mod_log_channel_id: str = Form(None),
    message_log_channel_id: str = Form(None),
    member_log_channel_id: str = Form(None),
    voice_log_channel_id: str = Form(None),
    ticket_category_id: str = Form(None),
    mod_role_id: str = Form(None),
    admin_role_id: str = Form(None),
    log_message_edits: str = Form("off"),
    log_message_deletions: str = Form("off"),
    log_member_joins: str = Form("off"),
    log_member_leaves: str = Form("off"),
    log_voice_updates: str = Form("off"),
    automod_invite_links: str = Form("off"),
    db: AsyncSession = Depends(get_db)
):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/")
    
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")

    result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
    config = result.scalar_one()
    
    def to_int(val):
        try:
            return int(val) if val and val.strip() else None
        except:
            return None

    config.log_channel_id = to_int(log_channel_id)
    config.mod_log_channel_id = to_int(mod_log_channel_id)
    config.message_log_channel_id = to_int(message_log_channel_id)
    config.member_log_channel_id = to_int(member_log_channel_id)
    config.voice_log_channel_id = to_int(voice_log_channel_id)
    config.ticket_category_id = to_int(ticket_category_id)
    config.mod_role_id = to_int(mod_role_id)
    config.admin_role_id = to_int(admin_role_id)
    
    config.log_message_edits = (log_message_edits == "on")
    config.log_message_deletions = (log_message_deletions == "on")
    config.log_member_joins = (log_member_joins == "on")
    config.log_member_leaves = (log_member_leaves == "on")
    config.log_voice_updates = (log_voice_updates == "on")
    config.automod_invite_links = (automod_invite_links == "on")
    
    await db.commit()
    return RedirectResponse(f"/guild/{guild_id}?success=true", status_code=303)

@app.post("/guild/{guild_id}/filters/add")
async def add_filter(request: Request, guild_id: int, phrase: str = Form(...), db: AsyncSession = Depends(get_db)):
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    clean_phrase = phrase.strip().lower()
    if not clean_phrase:
        return RedirectResponse(f"/guild/{guild_id}?tab=automod", status_code=303)

    # Check if exists
    result = await db.execute(select(WordFilter).where(WordFilter.guild_id == guild_id, WordFilter.phrase == clean_phrase))
    if result.scalar_one_or_none():
        return RedirectResponse(f"/guild/{guild_id}?tab=automod&error=duplicate", status_code=303)

    new_filter = WordFilter(guild_id=guild_id, phrase=clean_phrase)
    db.add(new_filter)
    await db.commit()
    return RedirectResponse(f"/guild/{guild_id}?success=true&tab=automod", status_code=303)

@app.get("/guild/{guild_id}/filters/delete/{filter_id}")
async def delete_filter(request: Request, guild_id: int, filter_id: int, db: AsyncSession = Depends(get_db)):
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    result = await db.execute(select(WordFilter).where(WordFilter.id == filter_id, WordFilter.guild_id == guild_id))
    filter_obj = result.scalar_one_or_none()
    if filter_obj:
        await db.delete(filter_obj)
        await db.commit()
    
    return RedirectResponse(f"/guild/{guild_id}?success=true", status_code=303)

@app.post("/guild/{guild_id}/reasons/add")
async def add_reason(
    request: Request, 
    guild_id: int, 
    label: str = Form(...), 
    category_id: int = Form(...),
    description: str = Form(None),
    emoji: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    new_reason = TicketReason(
        guild_id=guild_id, 
        label=label.strip(), 
        category_id=category_id, 
        description=description.strip() if description else None,
        emoji=emoji.strip() if emoji else None
    )
    db.add(new_reason)
    await db.commit()
    return RedirectResponse(f"/guild/{guild_id}?success=true&tab=tickets", status_code=303)

@app.get("/guild/{guild_id}/reasons/delete/{reason_id}")
async def delete_reason(request: Request, guild_id: int, reason_id: int, db: AsyncSession = Depends(get_db)):
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(str(g["id"]) == str(guild_id) for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    result = await db.execute(select(TicketReason).where(TicketReason.id == reason_id, TicketReason.guild_id == guild_id))
    reason_obj = result.scalar_one_or_none()
    if reason_obj:
        await db.delete(reason_obj)
        await db.commit()
    
    return RedirectResponse(f"/guild/{guild_id}?success=true&tab=tickets", status_code=303)

@app.get("/transcripts/{ticket_id}")
async def view_transcript(request: Request, ticket_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    
    if not ticket or not ticket.transcript_text:
        return PlainTextResponse("Transcript not found or access denied.", status_code=404)
        
    # Simple HTML wrapper for the transcript
    html_content = f"""
    <!DOCTYPE html>
    <html class="dark">
    <head>
        <title>Ticket #{ticket.id} Transcript</title>
        <style>
            body {{ font-family: sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 2rem; max_width: 800px; margin: 0 auto; }}
            .message {{ margin-bottom: 1rem; padding: 1rem; background: rgba(255,255,255,0.05); border-radius: 0.5rem; }}
            .author {{ font-weight: bold; color: #818cf8; margin-bottom: 0.25rem; display: block; }}
            h1 {{ border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 1rem; }}
        </style>
    </head>
    <body>
        <h1>Transcript: Ticket #{ticket.id}</h1>
        {ticket.transcript_text}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
