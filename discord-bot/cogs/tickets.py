import discord
from discord import app_commands
from discord.ext import commands
from database import db
from config import Config
import logging
import io
import os
import asyncio

# Views
class TicketLauncher(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="ticket_launch_btn")
    async def launch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TicketReasonSelect(interaction.guild.id)
        await view.populate_reasons()
        
        embed = discord.Embed(
            title="Ticket Reason Selection",
            description="Please choose the most appropriate reason for your ticket from the menu below to proceed.",
            color=Config.COLOR_NEUTRAL
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TicketReasonSelect(discord.ui.View):
    def __init__(self, guild_id):
        # Ephemeral views don't necessarily need to be persistent, 
        # but we keep timeout None for long-running selections.
        super().__init__(timeout=None)
        self.guild_id = guild_id

    async def populate_reasons(self):
        reasons = await db.fetch("SELECT id, label, description, emoji FROM ticket_reasons WHERE guild_id = $1", self.guild_id)
        if not reasons:
            self.select_reason.add_option(label="General Support", value="default", description="General inquiries", emoji="🎟️")
        else:
            for r in reasons:
                self.select_reason.add_option(
                    label=r['label'], 
                    value=str(r['id']), 
                    description=r['description'] or "No description", 
                    emoji=r['emoji'] or "🎟️"
                )

    @discord.ui.select(placeholder="Select a reason...", custom_id="launcher_select_reason")
    async def select_reason(self, interaction: discord.Interaction, select: discord.ui.Select):
        value = select.values[0]
        guild = interaction.guild
        
        # Determine category and staff roles
        target_category_id = None
        required_roles = []
        reason_label = "General Support"
        
        if value != "default":
            reason_data = await db.fetchrow("SELECT label, category_id, required_roles FROM ticket_reasons WHERE id = $1", int(value))
            if reason_data:
                reason_label = reason_data['label']
                target_category_id = reason_data['category_id']
                required_roles = reason_data['required_roles'] or []

        # Fallback category
        if not target_category_id:
            config = await db.fetchrow("SELECT ticket_category_id, mod_role_id, admin_role_id FROM guild_config WHERE guild_id = $1", guild.id)
            if config:
                target_category_id = config['ticket_category_id']

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        # Staff Roles
        config = await db.fetchrow("SELECT mod_role_id, admin_role_id FROM guild_config WHERE guild_id = $1", guild.id)
        if config:
            for r_id in [config['mod_role_id'], config['admin_role_id']]:
                if r_id:
                    role = guild.get_role(r_id)
                    if role: overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = guild.get_channel(target_category_id) if target_category_id else None
        
        # Respond to interaction immediately to avoid timeout/Responded errors
        await interaction.response.defer(ephemeral=True)
        
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites,
            category=category,
            reason=f"Ticket opened by {interaction.user}"
        )

        # Database record
        await db.execute(
            "INSERT INTO tickets (guild_id, channel_id, owner_id, reason_id) VALUES ($1, $2, $3, $4)",
            guild.id, ticket_channel.id, interaction.user.id, int(value) if value != "default" else None
        )

        # Welcome Embed
        embed = discord.Embed(
            title=f"Ticket: {reason_label}", 
            description=f"Hello {interaction.user.mention}, thank you for reaching out. Staff will assist you as soon as possible.",
            color=Config.COLOR_NEUTRAL,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Owner", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason_label, inline=True)
        embed.add_field(name="Status", value="Waiting for Staff", inline=False)
        
        await ticket_channel.send(embed=embed, view=TicketControls())

        await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.execute("UPDATE tickets SET claimed_by = $1 WHERE channel_id = $2", interaction.user.id, interaction.channel.id)
        
        embed = discord.Embed(
            title="Ticket Claimed",
            description=f"This ticket is now being handled by {interaction.user.mention}.",
            color=Config.COLOR_SUCCESS,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="In Progress", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        button.disabled = True
        button.label = "Claimed"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description="Are you sure you want to close this ticket?", color=Config.COLOR_ERROR)
        await interaction.response.send_message(embed=embed, view=TicketCloseConfirm(), ephemeral=True)


class TicketCloseConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        await db.execute("UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE channel_id = $1", channel.id)
        
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                await channel.set_permissions(target, read_messages=False)
        
        embed = discord.Embed(description="Ticket closed.", color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed, view=TicketManagement())


class TicketManagement(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript_btn")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        messages = [message async for message in channel.history(limit=5000, oldest_first=True)]
        
        html_content = "<html><body><h1>Ticket Transcript</h1>"
        for msg in messages:
            html_content += f"<p><strong>{msg.author}:</strong> {msg.content}</p>"
        html_content += "</body></html>"
        
        # Save to DB instead of file for web panel access
        transcript_text = html_content
        await db.execute("UPDATE tickets SET transcript_text = $1 WHERE channel_id = $2", transcript_text, channel.id)
        
        # Save as text file for download
        file = discord.File(io.BytesIO(html_content.encode('utf-8')), filename=f"transcript-{channel.name}.html")
        
        url = f"http://localhost:8000/transcripts/{channel.id}" # Base URL should be config, but hardcoded for local dev as web panel is local
        # We need the ticket ID, not channel ID for URL if we follow web panel logic, but map is 1:1 if we fetch right.
        # Actually web panel uses ticket.id (PK), so we need to fetch that.
        ticket_id = await db.fetchval("SELECT id FROM tickets WHERE channel_id = $1", channel.id)
        if ticket_id:
             url = f"http://localhost:8000/transcripts/{ticket_id}"

        embed = discord.Embed(description=f"Transcript saved.\n[View Online]({url})", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="ticket_delete_btn")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description="Deleting ticket in 5 seconds...", color=Config.COLOR_ERROR)
        await interaction.channel.send(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.primary, custom_id="ticket_reopen_btn")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        await db.execute("UPDATE tickets SET status = 'open', closed_at = NULL WHERE channel_id = $1", channel.id)
        
        ticket_data = await db.fetchrow("SELECT id, owner_id FROM tickets WHERE channel_id = $1", channel.id)
        
        users_to_add = set()
        msg_parts = []
        
        if ticket_data:
            owner_id = ticket_data['owner_id']
            ticket_id = ticket_data['id']
            users_to_add.add(owner_id)
            
            # Fetch added members
            members = await db.fetch("SELECT user_id FROM ticket_members WHERE ticket_id = $1", ticket_id)
            for m in members:
                users_to_add.add(m['user_id'])
            
            restored_count = 0
            for user_id in users_to_add:
                member = interaction.guild.get_member(user_id)
                if not member:
                    try:
                        member = await interaction.guild.fetch_member(user_id)
                    except discord.NotFound:
                        member = None
                
                if member:
                    await channel.set_permissions(member, read_messages=True, send_messages=True, attach_files=True)
                    restored_count += 1
            
            if restored_count > 0:
                 msg = f"Ticket reopened. Access restored for {restored_count} user(s)."
            else:
                 msg = "Ticket reopened, but no original members could be found."
        else:
             msg = "Ticket reopened (No DB record found)."
        
        embed_notify = discord.Embed(description=msg, color=Config.COLOR_SUCCESS)
        await channel.send(embed=embed_notify)

        await interaction.followup.send(embed=discord.Embed(description="Ticket reopened.", color=Config.COLOR_SUCCESS), ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views
        self.bot.add_view(TicketLauncher())
        self.bot.add_view(TicketControls())
        self.bot.add_view(TicketManagement())
        
    @app_commands.command(name="setup_ticket_panel", description="Send the professional ticket creation panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"Support Center - {guild.name}",
            description=(
                "Welcome to our server's support department. If you need assistance, please follow the instructions below:\n\n"
                "How to open a ticket:\n"
                "1. Click the button below to start the process.\n"
                "2. Select the most relevant reason from the menu that appears.\n"
                "3. A private channel will be created for you.\n\n"
                "Support is available during business hours. Please be patient while waiting for a response."
            ),
            color=Config.COLOR_NEUTRAL,
            timestamp=discord.utils.utcnow()
        )
        
        view = TicketLauncher()
        
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(embed=discord.Embed(description=f"Support panel successfully deployed in {channel.mention}", color=Config.COLOR_SUCCESS), ephemeral=True)

    @app_commands.command(name="ticket_panel", description="Resend the ticket control panel (for closed tickets)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if "ticket-" not in interaction.channel.name:
             return await interaction.response.send_message("Not a ticket channel.", ephemeral=True)
        
        embed = discord.Embed(description="Ticket Controls", color=Config.COLOR_NEUTRAL)
        # Determine view based on status? We assume closed if using this, or just generic management.
        # Actually ticket_panel implies the management view.
        await interaction.channel.send(embed=embed, view=TicketManagement())
        await interaction.response.send_message("Sent ticket controls.", ephemeral=True)

    @app_commands.command(name="add_ticket_reason", description="Add a new ticket reason")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_ticket_reason(self, interaction: discord.Interaction, label: str, category: discord.CategoryChannel, description: str = None, emoji: str = None):
        await db.execute(
            "INSERT INTO ticket_reasons (guild_id, label, category_id, description, emoji) VALUES ($1, $2, $3, $4, $5)",
            interaction.guild.id, label, category.id, description, emoji
        )
        await interaction.response.send_message(embed=discord.Embed(description=f"Added reason: `{label}`", color=Config.COLOR_SUCCESS), ephemeral=True)

    @app_commands.command(name="status_panel", description="Create a live status panel")
    async def status_panel(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        
        # Fetch ticket statistics
        total_tickets = await db.fetchval("SELECT COUNT(*) FROM tickets WHERE guild_id = $1", guild_id) or 0
        open_tickets = await db.fetchval("SELECT COUNT(*) FROM tickets WHERE guild_id = $1 AND status = 'open'", guild_id) or 0
        closed_tickets = await db.fetchval("SELECT COUNT(*) FROM tickets WHERE guild_id = $1 AND status = 'closed'", guild_id) or 0
        claimed_tickets = await db.fetchval("SELECT COUNT(*) FROM tickets WHERE guild_id = $1 AND claimed_by IS NOT NULL AND status = 'open'", guild_id) or 0
        unclaimed_tickets = open_tickets - claimed_tickets
        
        # Create the status embed
        embed = discord.Embed(
            title="📊 Ticket Status",
            description="Current ticket statistics for this server",
            color=Config.COLOR_NEUTRAL,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Total Tickets", value=f"```{total_tickets}```", inline=True)
        embed.add_field(name="Open Tickets", value=f"```{open_tickets}```", inline=True)
        embed.add_field(name="Closed Tickets", value=f"```{closed_tickets}```", inline=True)
        embed.add_field(name="Claimed", value=f"```{claimed_tickets}```", inline=True)
        embed.add_field(name="Unclaimed", value=f"```{unclaimed_tickets}```", inline=True)
        embed.add_field(name="Status", value="```✅ Active```", inline=True)
        
        embed.set_footer(text=f"Last updated")
        
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(embed=discord.Embed(description="Status panel created.", color=Config.COLOR_SUCCESS), ephemeral=True)


    @app_commands.command(name="add", description="Add a user to the current ticket")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        if "ticket-" not in interaction.channel.name:
            embed = discord.Embed(description="This command can only be used in ticket channels.", color=Config.COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
            
        ticket_id = await db.fetchval("SELECT id FROM tickets WHERE channel_id = $1", interaction.channel.id)
        if ticket_id:
             await db.execute("INSERT INTO ticket_members (ticket_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", ticket_id, user.id)
             
        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True)
        embed = discord.Embed(description=f"Added {user.mention} to the ticket.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove", description="Remove a user from the current ticket")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        if "ticket-" not in interaction.channel.name:
            embed = discord.Embed(description="This command can only be used in ticket channels.", color=Config.COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        ticket_id = await db.fetchval("SELECT id FROM tickets WHERE channel_id = $1", interaction.channel.id)
        if ticket_id:
             await db.execute("DELETE FROM ticket_members WHERE ticket_id = $1 AND user_id = $2", ticket_id, user.id)

        await interaction.channel.set_permissions(user, overwrite=None)
        embed = discord.Embed(description=f"Removed {user.mention} from the ticket.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rename", description="Rename the current ticket channel")
    async def rename_ticket(self, interaction: discord.Interaction, name: str):
        if "ticket-" not in interaction.channel.name:
            embed = discord.Embed(description="This command can only be used in ticket channels.", color=Config.COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        old_name = interaction.channel.name
        await interaction.channel.edit(name=f"ticket-{name}")
        embed = discord.Embed(description=f"Renamed channel from `{old_name}` to `ticket-{name}`.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
