import discord
from discord import app_commands
from discord.ext import commands
from database import db
from config import Config
import json

class SnippetSendModal(discord.ui.Modal, title="Fill Snippet Information"):
    def __init__(self, snippet_content, message_handle):
        super().__init__()
        self.snippet_content = snippet_content
        self.message_handle = message_handle # The interaction to follow up on
        
        # Parse placeholders from content and add text inputs dynamically
        # Simple implementation: assumes content has {placeholder}
        # For now, let's just add one generic input for "Extra Details" to append
        self.extra_details = discord.ui.TextInput(label="Extra Details", style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.extra_details)

    async def on_submit(self, interaction: discord.Interaction):
        # Construct final message
        final_content = self.snippet_content + f"\n\n{self.extra_details.value}"
        
        # Preview
        embed = discord.Embed(
            title="Snippet Preview",
            description=f"{final_content}\n\n*Do you want to send this snippet?*",
            color=Config.COLOR_NEUTRAL
        )
        await interaction.response.send_message(embed=embed, view=SnippetConfirmView(final_content), ephemeral=True)

class SnippetCreateModal(discord.ui.Modal, title="Create Snippet"):
    def __init__(self, name, category):
        super().__init__()
        self.name_val = name
        self.category_val = category
        
        self.content = discord.ui.TextInput(
            label="Snippet Content",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the message content here...",
            required=True,
            max_length=2000
        )
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        await db.execute(
            "INSERT INTO snippets (guild_id, name, category, content_json) VALUES ($1, $2, $3, $4)",
            interaction.guild.id, self.name_val, self.category_val, json.dumps({"content": self.content.value})
        )
        embed = discord.Embed(description=f"Snippet `{self.name_val}` created in category `{self.category_val}`.", color=Config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SnippetConfirmView(discord.ui.View):
    def __init__(self, content):
        super().__init__(timeout=60)
        self.content = content

    @discord.ui.button(label="Send", style=discord.ButtonStyle.green)
    async def send_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        snippet_embed = discord.Embed(description=self.content, color=Config.COLOR_NEUTRAL)
        await interaction.channel.send(embed=snippet_embed)
        embed = discord.Embed(description="Message sent.", color=Config.COLOR_SUCCESS)
        await interaction.response.edit_message(embed=embed, view=None)

class Snippets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_snippet", description="Create a reusable snippet")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_snippet(self, interaction: discord.Interaction, name: str, category: str):
        await interaction.response.send_modal(SnippetCreateModal(name, category))


    @app_commands.command(name="snippet", description="Send a snippet")
    @app_commands.checks.has_permissions(administrator=True)
    async def snippet(self, interaction: discord.Interaction, category: str):
        # Fetch snippets in category
        snippets = await db.fetch(
            "SELECT name, content_json FROM snippets WHERE guild_id = $1 AND category = $2",
            interaction.guild.id, category
        )
        
        if not snippets:
            embed = discord.Embed(description="No snippets found in this category.", color=Config.COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        view = discord.ui.View()
        select = discord.ui.Select(placeholder="Choose a snippet...")
        
        for s in snippets:
            content = json.loads(s['content_json']).get('content', '')
            select.add_option(label=s['name'], value=content[:100]) # storing content in value for simplicity, better to store ID
            
        async def callback(inter: discord.Interaction):
            selected_content = select.values[0]
            # Check for placeholders or just ask for details
            await inter.response.send_modal(SnippetSendModal(selected_content, inter))
            
        select.callback = callback
        view.add_item(select)
        
        embed = discord.Embed(description="Please select a message snippet to send:", color=Config.COLOR_NEUTRAL)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @snippet.autocomplete('category')
    @create_snippet.autocomplete('category')
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = await db.fetch("SELECT DISTINCT category FROM snippets WHERE guild_id = $1", interaction.guild.id)
        return [
            app_commands.Choice(name=c['category'], value=c['category'])
            for c in categories if current.lower() in c['category'].lower()
        ][:25]

    @app_commands.command(name="list_snippets", description="List all available snippets")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_snippets(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        snippets = await db.fetch("SELECT name, category FROM snippets WHERE guild_id = $1 ORDER BY category", interaction.guild.id)
        if not snippets:
            embed = discord.Embed(description="No snippets found.", color=Config.COLOR_ERROR)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        categories = {}
        for s in snippets:
            cat = s['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f"`{s['name']}`")
        
        embed = discord.Embed(title="Available Snippets", color=Config.COLOR_NEUTRAL)
        for cat, names in categories.items():
            embed.add_field(name=cat, value=", ".join(names), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="delete_snippet", description="Delete a snippet (choose from menu or type name)")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_snippet(self, interaction: discord.Interaction, name: str = None):
        if name:
            result = await db.execute("DELETE FROM snippets WHERE guild_id = $1 AND name = $2", interaction.guild.id, name)
            if result == "DELETE 0":
                embed = discord.Embed(description=f"Snippet `{name}` not found.", color=Config.COLOR_ERROR)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(description=f"Snippet `{name}` deleted.", color=Config.COLOR_SUCCESS)
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Show menu if no name provided
            snippets = await db.fetch("SELECT name, category FROM snippets WHERE guild_id = $1", interaction.guild.id)
            if not snippets:
                embed = discord.Embed(description="No snippets found to delete.", color=Config.COLOR_ERROR)
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            view = discord.ui.View()
            select = discord.ui.Select(placeholder="Select a snippet to delete...")
            
            for s in snippets:
                if len(select.options) >= 25:
                    break
                select.add_option(label=s['name'], value=s['name'], description=f"Category: {s['category']}")
                
            async def callback(inter: discord.Interaction):
                selected_name = select.values[0]
                await db.execute("DELETE FROM snippets WHERE guild_id = $1 AND name = $2", inter.guild.id, selected_name)
                embed = discord.Embed(description=f"Snippet `{selected_name}` has been deleted.", color=Config.COLOR_SUCCESS)
                await inter.response.edit_message(embed=embed, view=None)
                
            select.callback = callback
            view.add_item(select)
            embed = discord.Embed(description="Please select a snippet to delete from the menu below:", color=Config.COLOR_NEUTRAL)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @delete_snippet.autocomplete('name')
    async def name_autocomplete(self, interaction: discord.Interaction, current: str):
        names = await db.fetch("SELECT name, category FROM snippets WHERE guild_id = $1", interaction.guild.id)
        return [
            app_commands.Choice(name=f"{n['name']} ({n['category']})", value=n['name'])
            for n in names if current.lower() in n['name'].lower() or current.lower() in n['category'].lower()
        ][:25]


async def setup(bot):
    await bot.add_cog(Snippets(bot))
