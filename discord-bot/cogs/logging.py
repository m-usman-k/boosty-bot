import discord
from discord.ext import commands
from database import db
from config import Config
import datetime

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_to_db(self, guild_id, user_id, action_type, target_id=None, details=None):
        try:
            await db.execute(
                "INSERT INTO server_logs (guild_id, user_id, action_type, target_id, details) VALUES ($1, $2, $3, $4, $5)",
                guild_id, user_id, action_type, target_id, details
            )
        except Exception as e:
            print(f"Failed to log to DB: {e}")

    async def send_log_channel(self, guild, embed, log_type="general"):
        try:
            config = await db.fetchrow("SELECT * FROM guild_config WHERE guild_id = $1", guild.id)
            if not config:
                print(f"DEBUG: No config found for guild {guild.id}")
                return

            # Mapping types to columns
            channel_map = {
                "mod": "mod_log_channel_id",
                "message": "message_log_channel_id",
                "member": "member_log_channel_id",
                "voice": "voice_log_channel_id",
                "general": "log_channel_id"
            }

            target_key = channel_map.get(log_type, "log_channel_id")
            channel_id = config[target_key] if target_key in config.keys() else None
            
            # Fallback to general log channel if specific one isn't set
            if not channel_id:
                channel_id = config['log_channel_id']
            
            print(f"DEBUG: Attempting to log {log_type} to channel {channel_id} in {guild.id}")
            
            if channel_id:
                channel = guild.get_channel(channel_id)
                if not channel:
                    try:
                        print(f"DEBUG: Channel {channel_id} not in cache, fetching...")
                        channel = await guild.fetch_channel(channel_id)
                    except Exception as fe:
                        print(f"DEBUG: Fetch channel failed: {fe}")
                        channel = None
                        
                if channel:
                    await channel.send(embed=embed)
                else:
                    print(f"DEBUG: Could not find channel {channel_id}")
            else:
                print(f"DEBUG: No channel ID configured for {log_type} or fallback")
        except Exception as e:
            print(f"DEBUG: Error sending log: {e}")

    async def is_enabled(self, guild_id, facility):
        try:
            config = await db.fetchrow(f"SELECT {facility} FROM guild_config WHERE guild_id = $1", guild_id)
            status = config[facility] if (config and config[facility] is not None) else True
            print(f"DEBUG: Facility {facility} enabled status: {status}")
            return status
        except Exception as e:
            print(f"DEBUG: is_enabled check failed for {facility}: {e}")
            return True

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"DEBUG: Member joined guild {member.guild.id}")
        if not await self.is_enabled(member.guild.id, "log_member_joins"):
            return

        embed = discord.Embed(
            title="Member Joined", 
            description=f"{member.mention} `{member}`",
            color=Config.COLOR_SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await self.send_log_channel(member.guild, embed, "member")
        await self.log_to_db(member.guild.id, member.id, "member_join")
        
        # Suspect account
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - member.created_at
        if diff.days < 1:
            warn_embed = discord.Embed(
                title="Suspect Account Joined",
                description=f"User {member.mention} created account `{diff.seconds // 3600}` hours ago.",
                color=Config.COLOR_ERROR
            )
            await self.send_log_channel(member.guild, warn_embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # Check if it was a kick
        is_kick = False
        moderator = None
        reason = None
        
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                now = datetime.datetime.now(datetime.timezone.utc)
                if entry.target.id == member.id and (now - entry.created_at).total_seconds() < 10:
                    is_kick = True
                    moderator = entry.user
                    reason = entry.reason
                    break
        except Exception as e:
            print(f"DEBUG: Failed to check audit logs for kick: {e}")

        if is_kick:
            # Log as Kick
            embed = discord.Embed(
                title="Member Kicked",
                description=f"{member.mention} `{member}`",
                color=Config.COLOR_ERROR,
                timestamp=datetime.datetime.now()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Moderator", value=moderator.mention if moderator else "Unknown", inline=True)
            embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
            embed.set_footer(text=f"ID: {member.id}")
            
            await self.send_log_channel(member.guild, embed, "mod")
            await self.log_to_db(member.guild.id, member.id, "kick", details=f"By {moderator} for {reason}")
            
        else:
            # Log as Leave
            if not await self.is_enabled(member.guild.id, "log_member_leaves"):
                return
    
            embed = discord.Embed(
                title="Member Left", 
                description=f"{member.mention} `{member}`",
                color=Config.COLOR_ERROR,
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"ID: {member.id}")
            await self.send_log_channel(member.guild, embed, "member")
            await self.log_to_db(member.guild.id, member.id, "member_leave")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        moderator = None
        reason = None
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator = entry.user
                    reason = entry.reason
                    break
        except:
            pass
            
        embed = discord.Embed(
            title="Member Banned",
            description=f"{user.mention} `{user}`",
            color=Config.COLOR_ERROR,
            timestamp=datetime.datetime.now()
        )
        if isinstance(user, discord.User) or isinstance(user, discord.Member):
             embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(name="Moderator", value=moderator.mention if moderator else "Unknown", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        embed.set_footer(text=f"ID: {user.id}")

        await self.send_log_channel(guild, embed, "mod")
        await self.log_to_db(guild.id, user.id, "ban", details=f"By {moderator} for {reason}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    moderator = entry.user
                    break
        except:
            pass

        embed = discord.Embed(
            title="Member Unbanned",
            description=f"{user.mention} `{user}`",
            color=Config.COLOR_SUCCESS,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Moderator", value=moderator.mention if moderator else "Unknown", inline=True)
        embed.set_footer(text=f"ID: {user.id}")
        
        await self.send_log_channel(guild, embed, "mod")
        await self.log_to_db(guild.id, user.id, "unban", details=f"By {moderator}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Check for timeout changes
        if before.timed_out_until != after.timed_out_until:
            guild = after.guild
            if after.timed_out_until:
                # Timeout Added
                moderator = None
                reason = None
                try:
                    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                         if entry.target.id == after.id:
                             # We can't be 100% sure it's this entry easily without more checks but it's the best guess
                             moderator = entry.user
                             reason = entry.reason
                             break
                except:
                    pass
                
                embed = discord.Embed(
                    title="Member Timed Out",
                    description=f"{after.mention} `{after}`",
                    color=Config.COLOR_ERROR,
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="Duration", value=f"Until {discord.utils.format_dt(after.timed_out_until)}", inline=False)
                embed.add_field(name="Moderator", value=moderator.mention if moderator else "Unknown", inline=True)
                embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
                
                await self.send_log_channel(guild, embed, "mod")
                await self.log_to_db(guild.id, after.id, "timeout", details=f"Until {after.timed_out_until}")
            else:
                 # Timeout Removed
                embed = discord.Embed(
                    title="Timeout Removed",
                    description=f"{after.mention} `{after}`",
                    color=Config.COLOR_SUCCESS,
                    timestamp=datetime.datetime.now()
                )
                await self.send_log_channel(guild, embed, "mod")
                await self.log_to_db(guild.id, after.id, "remove_timeout")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        print(f"DEBUG: Message edit detected in {before.guild.id if before.guild else 'DM'}")
        if before.author.bot or before.content == after.content:
            return
        
        if not await self.is_enabled(before.guild.id, "log_message_edits"):
            return

        embed = discord.Embed(
            title="Message Edited", 
            description=f"In {before.channel.mention} by {before.author.mention}",
            color=Config.COLOR_NEUTRAL,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Before", value=f"`{before.content[:1000]}`" or "[No Content]", inline=False)
        embed.add_field(name="After", value=f"`{after.content[:1000]}`" or "[No Content]", inline=False)
        embed.add_field(name="Jump", value=f"[Link]({after.jump_url})", inline=False)
        
        await self.send_log_channel(before.guild, embed, "message")
        await self.log_to_db(before.guild.id, before.author.id, "message_edit", before.id, f"Chan: {before.channel.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        
        if not await self.is_enabled(message.guild.id, "log_message_deletions"):
            return

        embed = discord.Embed(
            title="Message Deleted", 
            description=f"In {message.channel.mention} by {message.author.mention}",
            color=Config.COLOR_ERROR,
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Content", value=f"`{message.content[:1000]}`" if message.content else "[No Content]", inline=False)
        
        # Handle Attachments
        if message.attachments:
            att_list = []
            for att in message.attachments:
                # Use proxy_url as it might persist slightly longer or be cached
                att_list.append(f"[{att.filename}]({att.proxy_url})")
            
            embed.add_field(name="Attachments", value="\n".join(att_list), inline=False)
            
            # Try to display first image
            if message.attachments[0].content_type and message.attachments[0].content_type.startswith("image/"):
                embed.set_image(url=message.attachments[0].proxy_url)
            
        await self.send_log_channel(message.guild, embed, "message")
        
        details = f"Content: {message.content[:200]}"
        if message.attachments:
            details += f" | {len(message.attachments)} attachments"
        
        await self.log_to_db(message.guild.id, message.author.id, "message_delete", message.id, details)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        
        if not await self.is_enabled(member.guild.id, "log_voice_updates"):
            return

        action = ""
        details = ""
        
        if before.channel is None:
            # Joined
            action = "voice_join"
            details = f"Joined {after.channel.name}"
            embed = discord.Embed(description=f"{member.mention} joined voice channel {after.channel.name}", color=Config.COLOR_SUCCESS)
        elif after.channel is None:
            # Left
            action = "voice_leave"
            details = f"Left {before.channel.name}"
            embed = discord.Embed(description=f"{member.mention} left voice channel {before.channel.name}", color=Config.COLOR_ERROR)
        else:
            # Moved
            action = "voice_move"
            details = f"Moved {before.channel.name} -> {after.channel.name}"
            embed = discord.Embed(description=f"{member.mention} moved from {before.channel.name} to {after.channel.name}", color=Config.COLOR_NEUTRAL)
            
        await self.send_log_channel(member.guild, embed, "voice")
        await self.log_to_db(member.guild.id, member.id, action, details=details)

    @discord.app_commands.command(name="logs", description="View recent server logs")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def view_logs(self, interaction: discord.Interaction, limit: int = 10):
        logs = await db.fetch("SELECT * FROM server_logs WHERE guild_id = $1 ORDER BY created_at DESC LIMIT $2", interaction.guild.id, limit)
        if not logs:
            embed = discord.Embed(description="No logs found.", color=Config.COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        description = ""
        for log in logs:
            user = self.bot.get_user(log['user_id']) or log['user_id']
            description += f"- **{log['action_type']}** | {user} | {log['details'] or ''}\n"
        
        embed = discord.Embed(title="Recent Logs", description=description[:4000], color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Logging(bot))
