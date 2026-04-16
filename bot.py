import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import os
import json
import asyncio
from datetime import datetime, timedelta

# ========== CONFIGURATION ==========
TOKEN = "YOUR_BOT_TOKEN_HERE"          # <-- Replace with your token
PREFIX = "/"
ADMIN_ROLE_NAME = "Admin"
INVITES_FILE = "invites.json"
WARNS_FILE = "warns.json"
TICKETS_FILE = "tickets.json"
# ===================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ---------- Invite tracking ----------
invite_data = {}

def load_invites():
    global invite_data
    if os.path.exists(INVITES_FILE):
        with open(INVITES_FILE, "r") as f:
            invite_data = json.load(f)
    else:
        invite_data = {}

def save_invites():
    with open(INVITES_FILE, "w") as f:
        json.dump(invite_data, f, indent=4)

def get_invite_count(guild_id, member_id):
    guild_str = str(guild_id)
    member_str = str(member_id)
    return invite_data.get(guild_str, {}).get(member_str, {}).get("invites", 0)

def add_invite(guild_id, inviter_id, invited_id):
    guild_str = str(guild_id)
    inviter_str = str(inviter_id)
    if guild_str not in invite_data:
        invite_data[guild_str] = {}
    if inviter_str not in invite_data[guild_str]:
        invite_data[guild_str][inviter_str] = {"invites": 0, "invited_users": []}
    invite_data[guild_str][inviter_str]["invites"] += 1
    invite_data[guild_str][inviter_str]["invited_users"].append(invited_id)
    save_invites()

invite_cache = {}

async def cache_invites(guild):
    try:
        invites = await guild.invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except:
        invite_cache[guild.id] = {}

# ---------- Ticket system storage ----------
ticket_config = {}  # guild_id: {"category_id": int, "support_role_id": int, "ticket_type": str, "templates": {}}

def load_tickets():
    global ticket_config
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r") as f:
            ticket_config = json.load(f)
    else:
        ticket_config = {}

def save_tickets():
    with open(TICKETS_FILE, "w") as f:
        json.dump(ticket_config, f, indent=4)

# ---------- Ticket creation helper ----------
async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    config = ticket_config.get(str(guild.id))
    if not config or "category_id" not in config:
        await interaction.response.send_message("Ticket system not set up. Ask an admin to run `/ticpanel create`.", ephemeral=True)
        return

    category = guild.get_channel(config["category_id"])
    if not category:
        await interaction.response.send_message("Ticket category not found.", ephemeral=True)
        return

    # Check for existing open ticket from this user
    for channel in guild.channels:
        if channel.category_id == config["category_id"] and channel.topic == str(interaction.user.id):
            await interaction.response.send_message(f"You already have an open ticket: {channel.mention}", ephemeral=True)
            return

    # Create ticket channel
    ticket_name = f"ticket-{interaction.user.name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    support_role = guild.get_role(config.get("support_role_id"))
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites, topic=str(interaction.user.id))

    embed = discord.Embed(title=f"Ticket: {ticket_type}", description=f"Support will be with you shortly.\nTicket created by {interaction.user.mention}", color=discord.Color.blue())
    embed.add_field(name="Type", value=ticket_type, inline=True)
    embed.add_field(name="Created", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)

    close_button = Button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    view = View()
    view.add_item(close_button)
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

# ---------- Button and Select components ----------
class TicketButton(Button):
    def __init__(self, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"ticket_{label}")

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.label)

class TicketSelect(Select):
    def __init__(self, options: list):
        select_options = [discord.SelectOption(label=opt, value=opt) for opt in options]
        super().__init__(placeholder="Select a ticket type", options=select_options)

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.values[0])

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="/help | ApexVoxel"))
    load_invites()
    load_tickets()
    for guild in bot.guilds:
        await cache_invites(guild)
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)

@bot.event
async def on_member_join(member):
    guild = member.guild
    try:
        new_invites = await guild.invites()
        old_invites = invite_cache.get(guild.id, {})
        inviter = None
        for invite in new_invites:
            old_uses = old_invites.get(invite.code, 0)
            if invite.uses > old_uses:
                inviter = invite.inviter
                break
        if inviter:
            add_invite(guild.id, inviter.id, member.id)
        await cache_invites(guild)
    except:
        pass

@bot.event
async def on_member_remove(member):
    await cache_invites(member.guild)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "close_ticket":
            channel = interaction.channel
            # Check permission: ticket owner or support role
            if channel.topic and int(channel.topic) == interaction.user.id:
                await interaction.response.send_message("Closing ticket...", ephemeral=True)
                await asyncio.sleep(3)
                await channel.delete()
            else:
                guild_id = str(interaction.guild.id)
                config = ticket_config.get(guild_id, {})
                support_role_id = config.get("support_role_id")
                if support_role_id and discord.utils.get(interaction.user.roles, id=support_role_id):
                    await interaction.response.send_message("Closing ticket...", ephemeral=True)
                    await asyncio.sleep(3)
                    await channel.delete()
                else:
                    await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)

# ---------- Helper for admin check ----------
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator or discord.utils.get(interaction.user.roles, name=ADMIN_ROLE_NAME)

# ========== SLASH COMMANDS ==========

# ----- General commands -----
@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="serverinfo", description="Show server information")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.blue())
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Get info about a user")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=member.display_name, color=member.color)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Joined Discord", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Show user's avatar")
async def slash_avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="membercount", description="Show member statistics")
async def slash_membercount(interaction: discord.Interaction):
    guild = interaction.guild
    humans = sum(1 for m in guild.members if not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    embed = discord.Embed(title="📊 Member Statistics", color=discord.Color.green())
    embed.add_field(name="Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="Humans", value=humans, inline=True)
    embed.add_field(name="Bots", value=bots, inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invites", description="Check how many people a user invited")
async def slash_invites(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    count = get_invite_count(interaction.guild.id, member.id)
    embed = discord.Embed(title=f"Invite Stats for {member.display_name}", color=discord.Color.blue())
    embed.add_field(name="Total Invites", value=count, inline=True)
    await interaction.response.send_message(embed=embed)

# ----- Moderation commands -----
@bot.tree.command(name="kick", description="Kick a member")
@commands.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked {member.mention} | Reason: {reason or 'No reason'}")

@bot.tree.command(name="ban", description="Ban a member")
@commands.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 Banned {member.mention} | Reason: {reason or 'No reason'}")

@bot.tree.command(name="softban", description="Ban + unban to delete messages")
@commands.has_permissions(ban_members=True)
async def slash_softban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.ban(reason=reason)
    await member.unban(reason="Softban")
    await interaction.response.send_message(f"🔄 Softbanned {member.mention} | Messages cleared")

@bot.tree.command(name="clear", description="Delete messages")
@commands.has_permissions(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, amount: int):
    if amount < 1:
        await interaction.response.send_message("Amount must be at least 1.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=min(amount, 100))
    await interaction.response.send_message(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member")
@commands.has_permissions(moderate_members=True)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = None):
    duration = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"⏱️ {member.mention} timed out for {minutes} minutes.")

@bot.tree.command(name="untimeout", description="Remove timeout from a member")
@commands.has_permissions(moderate_members=True)
async def slash_untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"✅ Removed timeout from {member.mention}")

@bot.tree.command(name="mute", description="Mute a member indefinitely")
@commands.has_permissions(moderate_members=True)
async def slash_mute(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    duration = discord.utils.utcnow() + timedelta(days=28)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 Muted {member.mention}")

@bot.tree.command(name="unmute", description="Unmute a member")
@commands.has_permissions(moderate_members=True)
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 Unmuted {member.mention}")

# ----- Warning system -----
@bot.tree.command(name="warn", description="Warn a member")
@commands.has_permissions(kick_members=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if os.path.exists(WARNS_FILE):
        with open(WARNS_FILE, "r") as f:
            warns = json.load(f)
    else:
        warns = {}
    guild_id = str(interaction.guild.id)
    member_id = str(member.id)
    if guild_id not in warns:
        warns[guild_id] = {}
    if member_id not in warns[guild_id]:
        warns[guild_id][member_id] = []
    warn_data = {
        "reason": reason or "No reason",
        "moderator": interaction.user.name,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    warns[guild_id][member_id].append(warn_data)
    with open(WARNS_FILE, "w") as f:
        json.dump(warns, f, indent=4)
    await interaction.response.send_message(f"⚠️ Warned {member.mention} | Total warns: {len(warns[guild_id][member_id])}")

@bot.tree.command(name="warnings", description="Show warnings for a member")
@commands.has_permissions(kick_members=True)
async def slash_warnings(interaction: discord.Interaction, member: discord.Member):
    if not os.path.exists(WARNS_FILE):
        await interaction.response.send_message("No warnings recorded.", ephemeral=True)
        return
    with open(WARNS_FILE, "r") as f:
        warns = json.load(f)
    guild_id = str(interaction.guild.id)
    member_id = str(member.id)
    if guild_id not in warns or member_id not in warns[guild_id]:
        await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
        return
    warn_list = warns[guild_id][member_id]
    embed = discord.Embed(title=f"Warnings for {member.display_name}", color=discord.Color.orange())
    embed.add_field(name="Total Warnings", value=len(warn_list), inline=False)
    for i, warn in enumerate(warn_list[-5:], 1):
        embed.add_field(name=f"Warning #{i}", value=f"Reason: {warn['reason']}\nMod: {warn['moderator']}\nTime: {warn['time']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarns", description="Clear all warnings for a member")
@commands.has_permissions(administrator=True)
async def slash_clearwarns(interaction: discord.Interaction, member: discord.Member):
    if os.path.exists(WARNS_FILE):
        with open(WARNS_FILE, "r") as f:
            warns = json.load(f)
        guild_id = str(interaction.guild.id)
        member_id = str(member.id)
        if guild_id in warns and member_id in warns[guild_id]:
            del warns[guild_id][member_id]
            with open(WARNS_FILE, "w") as f:
                json.dump(warns, f, indent=4)
            await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}")
        else:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
    else:
        await interaction.response.send_message("No warnings recorded.", ephemeral=True)

# ----- Channel management -----
@bot.tree.command(name="lock", description="Lock a channel")
@commands.has_permissions(manage_channels=True)
async def slash_lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(f"🔒 Locked {channel.mention}")

@bot.tree.command(name="unlock", description="Unlock a channel")
@commands.has_permissions(manage_channels=True)
async def slash_unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(f"🔓 Unlocked {channel.mention}")

@bot.tree.command(name="slowmode", description="Set slowmode in seconds")
@commands.has_permissions(manage_channels=True)
async def slash_slowmode(interaction: discord.Interaction, seconds: int, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await interaction.response.send_message(f"✅ Removed slowmode in {channel.mention}")
    else:
        await interaction.response.send_message(f"🐢 Set slowmode to {seconds} seconds in {channel.mention}")

# ----- Role management -----
@bot.tree.command(name="addrole", description="Add a role to a member")
@commands.has_permissions(manage_roles=True)
async def slash_addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Added {role.mention} to {member.mention}")

@bot.tree.command(name="removerole", description="Remove a role from a member")
@commands.has_permissions(manage_roles=True)
async def slash_removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ Removed {role.mention} from {member.mention}")

@bot.tree.command(name="nick", description="Change a member's nickname")
@commands.has_permissions(manage_nicknames=True)
async def slash_nick(interaction: discord.Interaction, member: discord.Member, nickname: str = None):
    old_nick = member.display_name
    await member.edit(nick=nickname)
    if nickname:
        await interaction.response.send_message(f"✏️ Changed {old_nick}'s nickname to {nickname}")
    else:
        await interaction.response.send_message(f"✏️ Reset {old_nick}'s nickname")

# ----- Utility commands -----
@bot.tree.command(name="say", description="Make the bot say something")
@commands.has_permissions(administrator=True)
async def slash_say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

@bot.tree.command(name="embed", description="Create an embed")
@commands.has_permissions(administrator=True)
async def slash_embed(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

# ----- Ticket system commands -----
@bot.tree.command(name="ticpanel", description="Create or remove ticket panel")
async def ticpanel(interaction: discord.Interaction, action: str, category: discord.CategoryChannel = None, role: discord.Role = None):
    if not is_admin(interaction):
        await interaction.response.send_message("You need admin permissions.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    if action.lower() == "create":
        if not category or not role:
            await interaction.response.send_message("Usage: `/ticpanel create category:#category role:@role`", ephemeral=True)
            return
        if guild_id not in ticket_config:
            ticket_config[guild_id] = {}
        ticket_config[guild_id]["category_id"] = category.id
        ticket_config[guild_id]["support_role_id"] = role.id
        save_tickets()
        await interaction.response.send_message(f"Ticket system set up! Category: {category.mention}, Support role: {role.mention}", ephemeral=True)
    elif action.lower() == "remove":
        if guild_id in ticket_config:
            del ticket_config[guild_id]
            save_tickets()
            await interaction.response.send_message("Ticket system removed.", ephemeral=True)
        else:
            await interaction.response.send_message("No ticket system configured.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid action. Use `create` or `remove`.", ephemeral=True)

@bot.tree.command(name="tictemplate", description="Create, list, or delete a ticket template")
async def tictemplate(interaction: discord.Interaction, action: str, name: str = None, description: str = None, options: str = None):
    if not is_admin(interaction):
        await interaction.response.send_message("You need admin permissions.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    if guild_id not in ticket_config:
        ticket_config[guild_id] = {}
    if "templates" not in ticket_config[guild_id]:
        ticket_config[guild_id]["templates"] = {}

    if action.lower() == "create":
        if not name or not description or not options:
            await interaction.response.send_message("Usage: `/tictemplate create name:<name> description:<desc> options:<opt1,opt2,opt3>`", ephemeral=True)
            return
        ticket_config[guild_id]["templates"][name] = {
            "description": description,
            "options": [opt.strip() for opt in options.split(",")]
        }
        save_tickets()
        await interaction.response.send_message(f"Template `{name}` created with options: {options}", ephemeral=True)
    elif action.lower() == "list":
        templates = ticket_config[guild_id].get("templates", {})
        if not templates:
            await interaction.response.send_message("No templates found.", ephemeral=True)
        else:
            msg = "**Templates:**\n" + "\n".join([f"- {n}: {d['options']}" for n, d in templates.items()])
            await interaction.response.send_message(msg, ephemeral=True)
    elif action.lower() == "delete":
        if not name:
            await interaction.response.send_message("Usage: `/tictemplate delete name:<name>`", ephemeral=True)
            return
        if name in ticket_config[guild_id].get("templates", {}):
            del ticket_config[guild_id]["templates"][name]
            save_tickets()
            await interaction.response.send_message(f"Template `{name}` deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("Template not found.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid action. Use `create`, `list`, or `delete`.", ephemeral=True)

@bot.tree.command(name="tictype", description="Set ticket type: button or menu")
async def tictype(interaction: discord.Interaction, ticket_type: str):
    if not is_admin(interaction):
        await interaction.response.send_message("You need admin permissions.", ephemeral=True)
        return
    if ticket_type.lower() not in ["button", "menu"]:
        await interaction.response.send_message("Type must be `button` or `menu`.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    if guild_id not in ticket_config:
        ticket_config[guild_id] = {}
    ticket_config[guild_id]["ticket_type"] = ticket_type.lower()
    save_tickets()
    await interaction.response.send_message(f"Ticket type set to `{ticket_type}`.", ephemeral=True)

@bot.tree.command(name="tichere", description="Send the ticket panel in this channel")
async def tichere(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("You need admin permissions.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    if guild_id not in ticket_config or "templates" not in ticket_config[guild_id] or not ticket_config[guild_id]["templates"]:
        await interaction.response.send_message("No ticket templates found. Create one with `/tictemplate create` first.", ephemeral=True)
        return

    templates = ticket_config[guild_id]["templates"]
    # Use the first template (you can extend to select template later)
    template_name = list(templates.keys())[0]
    template = templates[template_name]
    embed = discord.Embed(title="🎫 Support Tickets", description=template["description"], color=discord.Color.blue())
    view = View()

    if ticket_config[guild_id].get("ticket_type") == "menu":
        select = TicketSelect(template["options"])
        view.add_item(select)
    else:  # buttons
        for opt in template["options"]:
            view.add_item(TicketButton(opt))

    await interaction.response.send_message(embed=embed, view=view)

# ----- Help command -----
@bot.tree.command(name="help", description="Show all commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="ApexVoxel Bot Commands", color=discord.Color.gold())
    embed.add_field(name="📌 General", value="`/ping`, `/serverinfo`, `/userinfo`, `/avatar`, `/membercount`, `/invites`", inline=False)
    embed.add_field(name="🔨 Moderation", value="`/kick`, `/ban`, `/softban`, `/clear`, `/timeout`, `/untimeout`, `/mute`, `/unmute`", inline=False)
    embed.add_field(name="⚠️ Warnings", value="`/warn`, `/warnings`, `/clearwarns`", inline=False)
    embed.add_field(name="🔧 Channel", value="`/lock`, `/unlock`, `/slowmode`", inline=False)
    embed.add_field(name="👑 Role", value="`/addrole`, `/removerole`, `/nick`", inline=False)
    embed.add_field(name="📢 Utility", value="`/say`, `/embed`", inline=False)
    embed.add_field(name="🎫 Ticket System", value="`/ticpanel create`, `/ticpanel remove`, `/tictemplate`, `/tictype`, `/tichere`", inline=False)
    await interaction.response.send_message(embed=embed)

# ========== RUN BOT ==========
if __name__ == "__main__":
    bot.run(TOKEN)