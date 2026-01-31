import discord
from discord import app_commands
from discord.ext import commands
from database import db
from config import Config

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="config", description="Bot Configuration")

    logging_group = app_commands.Group(name="logging", description="Logging Configuration", parent=admin_group)

    @logging_group.command(name="set_channel", description="Set a specific log channel")
    @app_commands.describe(
        type="The type of log (general, mod, message, member, voice)",
        channel="The channel to send logs to"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="General (Fallback)", value="general"),
        app_commands.Choice(name="Moderation Actions", value="mod"),
        app_commands.Choice(name="Message Edits/Deletes", value="message"),
        app_commands.Choice(name="Member Join/Leave", value="member"),
        app_commands.Choice(name="Voice Updates", value="voice")
    ])
    async def set_log_channel(self, interaction: discord.Interaction, type: str, channel: discord.TextChannel):
        column = {
            "general": "log_channel_id",
            "mod": "mod_log_channel_id",
            "message": "message_log_channel_id",
            "member": "member_log_channel_id",
            "voice": "voice_log_channel_id"
        }.get(type)

        await db.execute(
            f"INSERT INTO guild_config (guild_id, {column}) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET {column} = $2",
            interaction.guild.id, channel.id
        )
        embed = discord.Embed(description=f"Log channel for **{type}** set to {channel.mention}", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @logging_group.command(name="toggle", description="Enable or disable a logging facility")
    @app_commands.choices(facility=[
        app_commands.Choice(name="Message Edits", value="log_message_edits"),
        app_commands.Choice(name="Message Deletions", value="log_message_deletions"),
        app_commands.Choice(name="Member Joins", value="log_member_joins"),
        app_commands.Choice(name="Member Leaves", value="log_member_leaves"),
        app_commands.Choice(name="Voice Updates", value="log_voice_updates")
    ])
    async def toggle_logging(self, interaction: discord.Interaction, facility: str, enabled: bool):
        await db.execute(
            f"INSERT INTO guild_config (guild_id, {facility}) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET {facility} = $2",
            interaction.guild.id, enabled
        )
        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(description=f"Facility **{facility.replace('log_', '').replace('_', ' ')}** is now **{status}**", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="set_transcripts", description="Set the transcript log channel")
    async def set_transcripts(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await db.execute(
            """INSERT INTO guild_config (guild_id, transcript_channel_id) VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET transcript_channel_id = $2""",
            interaction.guild.id, channel.id
        )
        embed = discord.Embed(description=f"Transcript channel set to {channel.mention}", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @admin_group.command(name="init", description="Initialize guild config")
    async def init(self, interaction: discord.Interaction):
        await db.execute(
            "INSERT INTO guild_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            interaction.guild.id
        )
        embed = discord.Embed(description="Guild configuration initialized.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="maintenance", description="Toggle maintenance mode")
    async def maintenance(self, interaction: discord.Interaction, enabled: bool):
        # We could store this in DB, for now just a mockup
        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(description=f"Maintenance mode **{status}**.", color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="info", description="View current bot configuration for this guild")
    async def config_info(self, interaction: discord.Interaction):
        config = await db.fetchrow("SELECT * FROM guild_config WHERE guild_id = $1", interaction.guild.id)
        if not config:
            embed = discord.Embed(description="Guild not initialized. Use `/config init`.", color=Config.COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = discord.Embed(title="Guild Configuration", color=Config.COLOR_NEUTRAL)
        
        # Channels
        embed.add_field(name="General Log", value=f"<#{config['log_channel_id']}>" if config['log_channel_id'] else "None", inline=True)
        embed.add_field(name="Mod Log", value=f"<#{config['mod_log_channel_id']}>" if config['mod_log_channel_id'] else "None", inline=True)
        embed.add_field(name="Message Log", value=f"<#{config['message_log_channel_id']}>" if config['message_log_channel_id'] else "None", inline=True)
        embed.add_field(name="Member Log", value=f"<#{config['member_log_channel_id']}>" if config['member_log_channel_id'] else "None", inline=True)
        embed.add_field(name="Voice Log", value=f"<#{config['voice_log_channel_id']}>" if config['voice_log_channel_id'] else "None", inline=True)
        embed.add_field(name="Transcript Log", value=f"<#{config['transcript_channel_id']}>" if config['transcript_channel_id'] else "None", inline=True)
        
        # Toggles
        toggles = []
        toggles.append(f"Message Edits: {'Enabled' if config['log_message_edits'] else 'Disabled'}")
        toggles.append(f"Message Deletions: {'Enabled' if config['log_message_deletions'] else 'Disabled'}")
        toggles.append(f"Member Joins: {'Enabled' if config['log_member_joins'] else 'Disabled'}")
        toggles.append(f"Member Leaves: {'Enabled' if config['log_member_leaves'] else 'Disabled'}")
        toggles.append(f"Voice Updates: {'Enabled' if config['log_voice_updates'] else 'Disabled'}")
        
        embed.add_field(name="Logging Facilities", value="\n".join(toggles), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
