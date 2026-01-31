import discord
from discord import app_commands
from discord.ext import commands
from database import db
from config import Config
import logging
import datetime
import typing

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_action(self, guild, moderator, user, action_type, reason=None):
        # Insert into DB (Punishments table)
        await db.execute(
            "INSERT INTO punishments (guild_id, user_id, moderator_id, type, reason) VALUES ($1, $2, $3, $4, $5)",
            guild.id, user.id, moderator.id, action_type, reason
        )
        # Also insert into generic logs for redundancy if needed, but punishments table is best for mod actions
        
        # Log to channel
        try:
            config = await db.fetchrow("SELECT log_channel_id, mod_log_channel_id FROM guild_config WHERE guild_id = $1", guild.id)
            channel_id = None
            if config:
                channel_id = config['mod_log_channel_id'] or config['log_channel_id']
            
            if channel_id:
                channel = guild.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await guild.fetch_channel(channel_id)
                    except:
                        channel = None
                
                if channel:
                    embed = discord.Embed(title=f"Action: {action_type}", color=Config.COLOR_ERROR, timestamp=datetime.datetime.now())
                    embed.add_field(name="User", value=f"`{user}` (`{user.id}`)", inline=True)
                    embed.add_field(name="Moderator", value=f"`{moderator}` (`{moderator.id}`)", inline=True)
                    embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"DEBUG: log_action failed: {e}")

    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        await self.log_action(interaction.guild, interaction.user, user, "warn", reason)
        try:
            embed = discord.Embed(description=f"You have been warned in `{interaction.guild.name}`.\nReason: `{reason}`", color=Config.COLOR_ERROR)
            await user.send(embed=embed)
        except:
            pass
        await interaction.response.send_message(embed=discord.Embed(description=f"Warned {user.mention}.", color=Config.COLOR_SUCCESS), ephemeral=True)



    @app_commands.command(name="purge", description="Delete multiple messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=discord.Embed(description=f"Deleted `{len(deleted)}` messages.", color=Config.COLOR_SUCCESS))
        
        # Log purge
        # Manual insert or log_action adaptation
        await db.execute(
            "INSERT INTO server_logs (guild_id, user_id, action_type, details) VALUES ($1, $2, $3, $4)",
            interaction.guild.id, interaction.user.id, "purge", f"Purged {len(deleted)} messages in {interaction.channel.name}"
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.guild: return
        
        config = await db.fetchrow("SELECT automod_invite_links FROM guild_config WHERE guild_id = $1", message.guild.id)
        if config and config['automod_invite_links']:
            # Automod: Invite Links
            if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
                await message.delete()
                embed = discord.Embed(description=f"{message.author.mention} No invite links allowed!", color=Config.COLOR_ERROR)
                await message.channel.send(embed=embed, delete_after=5)
                
                # Log Automod
                await self.log_action(message.guild, self.bot.user, message.author, "automod_invite", "Posted invite link")
        
        # Automod: Word Filters
        filters = await db.fetch("SELECT phrase FROM word_filters WHERE guild_id = $1", message.guild.id)
        for f in filters:
            if f['phrase'].lower() in message.content.lower():
                await message.delete()
                embed = discord.Embed(description=f"{message.author.mention} Your message contains a forbidden phrase!", color=Config.COLOR_ERROR)
                await message.channel.send(embed=embed, delete_after=5)
                await self.log_action(message.guild, self.bot.user, message.author, "automod_phrase", f"Phrase: {f['phrase']}")
                break

    @app_commands.command(name="lock", description="Lock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        embed = discord.Embed(description="This channel has been locked.", color=Config.COLOR_ERROR)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, interaction.user, interaction.guild.me, "lock", f"Locked {interaction.channel.name}")

    @app_commands.command(name="unlock", description="Unlock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        embed = discord.Embed(description="This channel has been unlocked.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, interaction.user, interaction.guild.me, "unlock", f"Unlocked {interaction.channel.name}")

    @app_commands.command(name="slowmode", description="Set the slowmode for the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        await interaction.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(description=f"Slowmode set to `{seconds}` seconds.", color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed)
        await self.log_action(interaction.guild, interaction.user, interaction.guild.me, "slowmode", f"Set to {seconds}s in {interaction.channel.name}")

    @app_commands.command(name="nick", description="Change a user's nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, user: discord.Member, nickname: str = None):
        old_nick = user.display_name
        await user.edit(nick=nickname)
        embed = discord.Embed(description=f"Changed {user.mention}'s nickname to `{nickname if nickname else 'Reset'}`.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.log_action(interaction.guild, interaction.user, user, "nickname", f"Changed from {old_nick} to {nickname if nickname else 'Reset'}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
