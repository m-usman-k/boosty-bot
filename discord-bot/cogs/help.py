import discord
from discord import app_commands
from discord.ext import commands
import datetime
from config import Config

# Removed Emojis
COG_LABELS = {
    "Tickets": "Tickets",
    "Moderation": "Moderation",
    "Admin": "Admin",
    "Logging": "Logging",
    "Snippets": "Snippets",
    "Help": "Help"
}

class HelpSelect(discord.ui.Select):
    def __init__(self, categories):
        options = []
        
        for cog_name, cog in categories.items():
            label = COG_LABELS.get(cog_name, cog_name)
            desc = cog.description or "No description provided."
            if len(desc) > 90:
                desc = desc[:87] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                value=cog_name,
                description=desc
            ))

        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await self.view.update_selection(interaction, self.values[0])

class HelpView(discord.ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=120)
        self.bot = bot
        self.author = author
        self.cogs = {name: cog for name, cog in bot.cogs.items() if len(cog.get_app_commands()) > 0}
        self.cog_names = list(self.cogs.keys())
        self.current_page = self.cog_names[0] if self.cog_names else None
        
        self.add_item(HelpSelect(self.cogs))
        
        self.prev_btn = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=True)
        self.prev_btn.callback = self.prev_page
        self.add_item(self.prev_btn)
        
        self.next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.next_btn.callback = self.next_page
        self.add_item(self.next_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            embed = discord.Embed(description="This menu is for the command author only.", color=Config.COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    async def update_buttons(self):
        try:
            idx = self.cog_names.index(self.current_page)
            self.prev_btn.disabled = (idx == 0)
            self.next_btn.disabled = (idx == len(self.cog_names) - 1)
        except ValueError:
            self.prev_btn.disabled = True
            self.next_btn.disabled = True

    async def prev_page(self, interaction: discord.Interaction):
        idx = self.cog_names.index(self.current_page)
        if idx > 0:
            target = self.cog_names[idx - 1]
            await self.update_selection(interaction, target)

    async def next_page(self, interaction: discord.Interaction):
        idx = self.cog_names.index(self.current_page)
        if idx < len(self.cog_names) - 1:
            target = self.cog_names[idx + 1]
            await self.update_selection(interaction, target)

    async def update_selection(self, interaction: discord.Interaction, selection):
        self.current_page = selection
        await self.update_buttons()
        embed = self.get_embed(selection)
        await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self, selection):
        cog = self.cogs.get(selection)
        if not cog:
            return discord.Embed(description="No commands found.", color=Config.COLOR_ERROR)

        label = COG_LABELS.get(selection, selection)
        embed = discord.Embed(
            title=f"{label} Commands",
            description=cog.description if cog.description else f"List of available {label} commands:",
            color=Config.COLOR_NEUTRAL
        )
        
        # Helper to get all commands including subcommands
        all_commands = []
        for cmd in cog.get_app_commands():
            if isinstance(cmd, app_commands.Group):
                for sub_cmd in cmd.walk_commands():
                    all_commands.append(sub_cmd)
            else:
                all_commands.append(cmd)

        if not all_commands:
            embed.add_field(name="Empty", value="No commands found.", inline=False)
        else:
            cmd_list = []
            for cmd in all_commands:
                desc = cmd.description or "No description"
                # For subcommands, show the full path (e.g., /config info)
                full_name = cmd.qualified_name
                cmd_list.append(f"`/{full_name}` — {desc}")
            
            # Single field for all commands in the category
            embed.add_field(name=f"{label} Modules", value="\n".join(cmd_list), inline=False)
        
        embed.set_footer(text=f"Viewing {label} category - Total: {len(all_commands)}")
        return embed

class Help(commands.Cog):
    """
    View help and available commands.
    """
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show the help menu")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = HelpView(self.bot, interaction.user)
        if view.current_page:
            embed = view.get_embed(view.current_page)
            await view.update_buttons()
            await interaction.followup.send(embed=embed, view=view)
        else:
            embed = discord.Embed(description="No commands available.", color=Config.COLOR_ERROR)
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        embed = discord.Embed(description=f"Pong! Latency: `{round(self.bot.latency * 1000)}ms`", color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Get information about a user")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        user = user or interaction.user
        embed = discord.Embed(title=f"User Info - {user}", color=Config.COLOR_NEUTRAL)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=False)
        embed.add_field(name="Joined Discord", value=discord.utils.format_dt(user.created_at, "R"), inline=False)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(user.joined_at, "R"), inline=False)
        embed.add_field(name="Roles", value=", ".join([role.mention for role in user.roles[1:][:10]]) or "None", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="serverinfo", description="Get information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        embed = discord.Embed(title=f"Server Info - {guild.name}", color=Config.COLOR_NEUTRAL)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=f"{guild.owner.mention}", inline=False)
        embed.add_field(name="Members", value=f"`{guild.member_count}`", inline=False)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"), inline=False)
        embed.add_field(name="Channels", value=f"`{len(guild.channels)}`", inline=False)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=False)
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
