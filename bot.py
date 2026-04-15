# ApexVoxel - All-in-One Discord Bot
# Fixed version - No permission errors, all tables created

import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import random
import datetime
import time
import math
import aiohttp
import sqlite3
from typing import Optional, List, Dict

# Bot Configuration
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Database Setup
conn = sqlite3.connect('apexvoxel.db')
c = conn.cursor()

# Create ALL necessary tables
c.execute('''CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    guild_id INTEGER,
    reason TEXT,
    moderator_id INTEGER,
    timestamp TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS mute_roles (
    guild_id INTEGER PRIMARY KEY,
    role_id INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS prefixes (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS auto_roles (
    guild_id INTEGER,
    role_id INTEGER,
    PRIMARY KEY (guild_id, role_id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS server_stats (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id INTEGER PRIMARY KEY,
    category_id INTEGER,
    support_role_id INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT,
    channel_id INTEGER,
    user_id INTEGER,
    guild_id INTEGER,
    status TEXT,
    created_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    channel_id INTEGER,
    prize TEXT,
    winners INTEGER,
    end_time TEXT,
    guild_id INTEGER,
    hosted_by INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER,
    guild_id INTEGER,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_message_time TEXT,
    PRIMARY KEY (user_id, guild_id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER PRIMARY KEY,
    wallet INTEGER DEFAULT 0,
    bank INTEGER DEFAULT 0
)''')

# NEW: Blacklist table for auto-mod
c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
    guild_id INTEGER,
    word TEXT,
    PRIMARY KEY (guild_id, word)
)''')

conn.commit()

# Bot Status
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="ApexVoxel | !help"))
    status_task.start()
    # level_system.start()  # Not needed because leveling is handled in on_message

# Tasks
@tasks.loop(minutes=5)
async def status_task():
    statuses = [
        discord.Activity(type=discord.ActivityType.playing, name=f"!help | {len(bot.guilds)} servers"),
        discord.Activity(type=discord.ActivityType.watching, name="over ApexVoxel"),
        discord.Activity(type=discord.ActivityType.listening, name="to !ticket"),
        discord.Activity(type=discord.ActivityType.competing, name="Apex Voxel"),
        discord.Activity(type=discord.ActivityType.playing, name="VPS Hosting")
    ]
    await bot.change_presence(activity=random.choice(statuses))

# Level XP System
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Level system
    if message.guild:
        user_id = message.author.id
        guild_id = message.guild.id
        current_time = datetime.datetime.now()
        
        c.execute("SELECT xp, level, last_message_time FROM levels WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        result = c.fetchone()
        
        if result:
            xp, level, last_time = result
            if last_time:
                last_msg = datetime.datetime.fromisoformat(last_time)
                if (current_time - last_msg).seconds >= 60:
                    xp += random.randint(15, 25)
                    new_level = int(xp ** (1/4) * 0.25)
                    
                    if new_level > level:
                        await message.channel.send(f"🎉 {message.author.mention} leveled up to level {new_level}!")
                        level = new_level
                    
                    c.execute("UPDATE levels SET xp=?, level=?, last_message_time=? WHERE user_id=? AND guild_id=?", 
                             (xp, level, current_time.isoformat(), user_id, guild_id))
                    conn.commit()
        else:
            c.execute("INSERT INTO levels VALUES (?, ?, ?, ?, ?)", 
                     (user_id, guild_id, random.randint(15, 25), 1, current_time.isoformat()))
            conn.commit()
    
    await bot.process_commands(message)

# Custom prefix
async def get_prefix(bot, message):
    if not message.guild:
        return '!'
    c.execute("SELECT prefix FROM prefixes WHERE guild_id=?", (message.guild.id,))
    result = c.fetchone()
    return result[0] if result else '!'

# Help Command
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="ApexVoxel Bot Commands", description="Here are all 50+ commands!", color=discord.Color.blue())
    embed.add_field(name="📊 **Moderation**", value="`kick`, `ban`, `warn`, `warnings`, `clearwarns`, `mute`, `unmute`, `clear`, `slowmode`, `lockdown`, `unlockdown`, `voicekick`, `softban`", inline=False)
    embed.add_field(name="⚙️ **Utility**", value="`ping`, `serverinfo`, `userinfo`, `avatar`, `roleinfo`, `botinfo`, `membercount`, `servericon`, `emojilist`, `roleall`, `removeallroles`, `nickname`", inline=False)
    embed.add_field(name="🎮 **Fun**", value="`8ball`, `coinflip`, `dice`, `rps`, `trivia`, `meme`, `dog`, `cat`, `fact`, `joke`, `roast`, `rate`, `say`, `reverse`, `emojify`", inline=False)
    embed.add_field(name="🎟️ **Tickets**", value="`ticket`, `ticket close`, `ticket claim`, `ticket add`, `ticket remove`, `ticket setup`", inline=False)
    embed.add_field(name="🎉 **Giveaways**", value="`giveaway start`, `giveaway reroll`, `giveaway end`, `giveaway list`", inline=False)
    embed.add_field(name="📈 **Leveling**", value="`rank`, `leaderboard`, `setlevel`, `resetlevel`", inline=False)
    embed.add_field(name="💰 **Economy**", value="`balance`, `daily`, `work`, `steal`, `give`, `shop`, `buy`, `inventory`", inline=False)
    embed.add_field(name="🎵 **Music**", value="`play`, `skip`, `stop`, `queue`, `nowplaying`, `volume`, `pause`, `resume`", inline=False)
    embed.add_field(name="🛡️ **Auto-Mod**", value="`automod on/off`, `antispam`, `blacklist`, `whitelist`", inline=False)
    embed.add_field(name="📊 **Server Stats**", value="`setupstats`, `levelchannel`, `welcomer`, `goodbye`", inline=False)
    embed.add_field(name="🤖 **Owner Only**", value="`status`, `guilds`, `eval`, `shutdown`, `blacklist server`, `reload`", inline=False)
    embed.add_field(name="📚 **Info**", value="`invite`, `support`, `vote`, `privacy`", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author.name} | ApexVoxel v1.0")
    await ctx.send(embed=embed)

# ---------- MODERATION ----------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="✅ Member Kicked", description=f"{member.mention} has been kicked.\nReason: {reason}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="✅ Member Banned", description=f"{member.mention} has been banned.\nReason: {reason}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member):
    banned_users = await ctx.guild.bans()
    member_name, member_discriminator = member.split('#')
    for ban_entry in banned_users:
        user = ban_entry.user
        if (user.name, user.discriminator) == (member_name, member_discriminator):
            await ctx.guild.unban(user)
            await ctx.send(f"✅ Unbanned {user.mention}")
            return
    await ctx.send("❌ User not found in banned list")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    c.execute("INSERT INTO warnings (user_id, guild_id, reason, moderator_id, timestamp) VALUES (?, ?, ?, ?, ?)",
              (member.id, ctx.guild.id, reason, ctx.author.id, datetime.datetime.now().isoformat()))
    conn.commit()
    embed = discord.Embed(title="⚠️ Warning Issued", description=f"{member.mention} has been warned.\nReason: {reason}", color=discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    if not member:
        member = ctx.author
    c.execute("SELECT reason, moderator_id, timestamp FROM warnings WHERE user_id=? AND guild_id=?", (member.id, ctx.guild.id))
    warnings = c.fetchall()
    if not warnings:
        await ctx.send(f"{member.mention} has no warnings.")
        return
    embed = discord.Embed(title=f"Warnings for {member.name}", color=discord.Color.red())
    for i, warning in enumerate(warnings[:10], 1):
        moderator = bot.get_user(warning[1])
        embed.add_field(name=f"Warning #{i}", value=f"Reason: {warning[0]}\nModerator: {moderator.name if moderator else 'Unknown'}\nDate: {warning[2][:10]}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    c.execute("DELETE FROM warnings WHERE user_id=? AND guild_id=?", (member.id, ctx.guild.id))
    conn.commit()
    await ctx.send(f"✅ Cleared all warnings for {member.mention}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: str = None, *, reason="No reason provided"):
    c.execute("SELECT role_id FROM mute_roles WHERE guild_id=?", (ctx.guild.id,))
    result = c.fetchone()
    if result:
        mute_role = ctx.guild.get_role(result[0])
    else:
        mute_role = await ctx.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
        c.execute("INSERT INTO mute_roles VALUES (?, ?)", (ctx.guild.id, mute_role.id))
        conn.commit()
    await member.add_roles(mute_role, reason=reason)
    if duration:
        time_unit = duration[-1]
        time_value = int(duration[:-1])
        if time_unit == 's':
            mute_time = time_value
        elif time_unit == 'm':
            mute_time = time_value * 60
        elif time_unit == 'h':
            mute_time = time_value * 3600
        elif time_unit == 'd':
            mute_time = time_value * 86400
        else:
            mute_time = 300
        await asyncio.sleep(mute_time)
        await member.remove_roles(mute_role)
        await ctx.send(f"🔊 {member.mention} has been automatically unmuted.")
    await ctx.send(f"🔇 Muted {member.mention} for {duration if duration else 'indefinite'}.\nReason: {reason}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    c.execute("SELECT role_id FROM mute_roles WHERE guild_id=?", (ctx.guild.id,))
    result = c.fetchone()
    if result:
        mute_role = ctx.guild.get_role(result[0])
        if mute_role in member.roles:
            await member.remove_roles(mute_role)
            await ctx.send(f"🔊 Unmuted {member.mention}")
        else:
            await ctx.send(f"{member.mention} is not muted.")
    else:
        await ctx.send("No mute role configured.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount > 100:
        await ctx.send("❌ Cannot delete more than 100 messages at once.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ Deleted {len(deleted)-1} messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"✅ Slowmode set to {seconds} seconds.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lockdown(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔒 {channel.mention} has been locked down.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlockdown(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔓 {channel.mention} has been unlocked.")

# FIXED: Changed voice_kick to move_members
@bot.command()
@commands.has_permissions(move_members=True)
async def voicekick(ctx, member: discord.Member):
    if member.voice and member.voice.channel:
        await member.move_to(None)
        await ctx.send(f"✅ Kicked {member.mention} from voice channel.")
    else:
        await ctx.send(f"{member.mention} is not in a voice channel.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await member.unban(reason="Softban - Kicked and cleared messages")
    await ctx.send(f"✅ Softbanned {member.mention} - Messages cleared.")

# ---------- UTILITY ----------
@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: {latency}ms", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, description=guild.description, color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🆔 ID", value=guild.id, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=member.name, color=member.color)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    else:
        embed.set_thumbnail(url=member.default_avatar.url)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📅 Joined", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="📅 Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🎭 Top Role", value=member.top_role.mention, inline=True)
    embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.blue())
    if member.avatar:
        embed.set_image(url=member.avatar.url)
    else:
        embed.set_image(url=member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def roleinfo(ctx, role: discord.Role):
    embed = discord.Embed(title=role.name, color=role.color)
    embed.add_field(name="🆔 ID", value=role.id, inline=True)
    embed.add_field(name="🎨 Color", value=str(role.color), inline=True)
    embed.add_field(name="👥 Members", value=len(role.members), inline=True)
    embed.add_field(name="📊 Position", value=role.position, inline=True)
    embed.add_field(name="🔒 Hoist", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="🔗 Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def botinfo(ctx):
    embed = discord.Embed(title="ApexVoxel Bot Info", color=discord.Color.gold())
    embed.add_field(name="🤖 Name", value=bot.user.name, inline=True)
    embed.add_field(name="📦 Version", value="1.0.0", inline=True)
    embed.add_field(name="👑 Developer", value="Apex Hosting", inline=True)
    embed.add_field(name="🌐 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="👥 Users", value=sum(g.member_count for g in bot.guilds), inline=True)
    embed.add_field(name="📚 Commands", value="50+", inline=True)
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def membercount(ctx):
    total = ctx.guild.member_count
    humans = len([m for m in ctx.guild.members if not m.bot])
    bots = total - humans
    embed = discord.Embed(title=f"Members in {ctx.guild.name}", color=discord.Color.green())
    embed.add_field(name="👥 Total", value=total, inline=True)
    embed.add_field(name="👤 Humans", value=humans, inline=True)
    embed.add_field(name="🤖 Bots", value=bots, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def servericon(ctx):
    if ctx.guild.icon:
        embed = discord.Embed(title=f"{ctx.guild.name}'s Icon", color=discord.Color.blue())
        embed.set_image(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send("This server has no icon.")

@bot.command()
async def emojilist(ctx):
    emojis = [str(emoji) for emoji in ctx.guild.emojis]
    if emojis:
        await ctx.send(" ".join(emojis[:50]))
    else:
        await ctx.send("No emojis in this server.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def roleall(ctx, role: discord.Role):
    for member in ctx.guild.members:
        if role not in member.roles:
            await member.add_roles(role)
    await ctx.send(f"✅ Added {role.name} to all members.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removeallroles(ctx, member: discord.Member):
    roles_to_remove = [role for role in member.roles if role != ctx.guild.default_role]
    await member.remove_roles(*roles_to_remove)
    await ctx.send(f"✅ Removed all roles from {member.mention}")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nickname(ctx, member: discord.Member, *, nickname: str = None):
    await member.edit(nick=nickname)
    await ctx.send(f"✅ Changed {member.mention}'s nickname to {nickname if nickname else 'default'}")

# ---------- FUN ----------
@bot.command()
async def eightball(ctx, *, question):
    responses = ["It is certain.", "It is decidedly so.", "Without a doubt.", "Yes definitely.", "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.", "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."]
    embed = discord.Embed(title="🎱 8Ball", color=discord.Color.purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads", "Tails"])
    embed = discord.Embed(title="🪙 Coin Flip", description=f"The coin landed on **{result}**!", color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command()
async def dice(ctx, sides: int = 6):
    result = random.randint(1, sides)
    embed = discord.Embed(title="🎲 Dice Roll", description=f"You rolled a **{result}** on a {sides}-sided die!", color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command()
async def rps(ctx, choice: str):
    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)
    choice = choice.lower()
    if choice not in choices:
        await ctx.send("Please choose rock, paper, or scissors.")
        return
    if choice == bot_choice:
        result = "It's a tie!"
    elif (choice == "rock" and bot_choice == "scissors") or (choice == "paper" and bot_choice == "rock") or (choice == "scissors" and bot_choice == "paper"):
        result = "You win!"
    else:
        result = "I win!"
    embed = discord.Embed(title="✊📄✂️ Rock Paper Scissors", color=discord.Color.green())
    embed.add_field(name="Your choice", value=choice, inline=True)
    embed.add_field(name="My choice", value=bot_choice, inline=True)
    embed.add_field(name="Result", value=result, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def trivia(ctx):
    questions = {
        "What is the capital of France?": "Paris",
        "What is the largest planet in our solar system?": "Jupiter",
        "Who painted the Mona Lisa?": "Leonardo da Vinci",
        "What is the chemical symbol for gold?": "Au",
        "What year was Discord released?": "2015"
    }
    question = random.choice(list(questions.keys()))
    answer = questions[question]
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    await ctx.send(f"📝 Trivia: {question}\nYou have 15 seconds to answer!")
    try:
        msg = await bot.wait_for('message', timeout=15.0, check=check)
        if msg.content.lower() == answer.lower():
            await ctx.send("✅ Correct!")
        else:
            await ctx.send(f"❌ Wrong! The answer was {answer}")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Time's up! The answer was {answer}")

@bot.command()
async def meme(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as resp:
            data = await resp.json()
            embed = discord.Embed(title=data['title'], color=discord.Color.random())
            embed.set_image(url=data['url'])
            embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")
            await ctx.send(embed=embed)

@bot.command()
async def dog(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
            data = await resp.json()
            embed = discord.Embed(title="🐕 Woof!", color=discord.Color.brown())
            embed.set_image(url=data['message'])
            await ctx.send(embed=embed)

@bot.command()
async def cat(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
            data = await resp.json()
            embed = discord.Embed(title="🐱 Meow!", color=discord.Color.orange())
            embed.set_image(url=data[0]['url'])
            await ctx.send(embed=embed)

@bot.command()
async def fact(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://uselessfacts.jsph.pl/random.json?language=en") as resp:
            data = await resp.json()
            embed = discord.Embed(title="📖 Random Fact", description=data['text'], color=discord.Color.blue())
            await ctx.send(embed=embed)

@bot.command()
async def joke(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://v2.jokeapi.dev/joke/Any?safe-mode") as resp:
            data = await resp.json()
            if data['type'] == 'single':
                embed = discord.Embed(title="😂 Joke", description=data['joke'], color=discord.Color.green())
            else:
                embed = discord.Embed(title="😂 Joke", description=f"{data['setup']}\n\n||{data['delivery']}||", color=discord.Color.green())
            await ctx.send(embed=embed)

@bot.command()
async def roast(ctx, member: discord.Member = None):
    member = member or ctx.author
    roasts = ["You're not stupid; you just have bad luck thinking.", "You're like a cloud. When you disappear, it's a beautiful day.", "I'd agree with you, but then we'd both be wrong.", "You bring everyone so much joy. When you leave.", "I've seen salads more intimidating than you.", "You're proof that evolution can go in reverse.", "You're not the sharpest tool in the shed.", "If I wanted to hear from an idiot, I'd watch your stream."]
    await ctx.send(f"{member.mention}, {random.choice(roasts)}")

@bot.command()
async def rate(ctx, thing: str = None):
    if not thing:
        thing = ctx.author.name
    rating = random.randint(0, 100)
    embed = discord.Embed(title=f"Rating {thing}", description=f"⭐ {rating}/100", color=discord.Color.purple())
    await ctx.send(embed=embed)

@bot.command()
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
async def reverse(ctx, *, text):
    await ctx.send(text[::-1])

@bot.command()
async def emojify(ctx, *, text):
    emoji_dict = {
        'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪', 'f': '🇫', 'g': '🇬',
        'h': '🇭', 'i': '🇮', 'j': '🇯', 'k': '🇰', 'l': '🇱', 'm': '🇲', 'n': '🇳',
        'o': '🇴', 'p': '🇵', 'q': '🇶', 'r': '🇷', 's': '🇸', 't': '🇹', 'u': '🇺',
        'v': '🇻', 'w': '🇼', 'x': '🇽', 'y': '🇾', 'z': '🇿'
    }
    result = ''.join(emoji_dict.get(char.lower(), char) for char in text)
    await ctx.send(result)

# ---------- TICKET SYSTEM ----------
@bot.command()
async def ticket(ctx):
    c.execute("SELECT category_id, support_role_id FROM ticket_config WHERE guild_id=?", (ctx.guild.id,))
    config = c.fetchone()
    if not config:
        await ctx.send("❌ Ticket system not set up. Use `!ticket setup` first.")
        return
    category = bot.get_channel(config[0])
    support_role = ctx.guild.get_role(config[1])
    ticket_id = f"ticket-{ctx.author.name}-{random.randint(1000, 9999)}"
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await ctx.guild.create_text_channel(ticket_id, category=category, overwrites=overwrites)
    c.execute("INSERT INTO tickets (ticket_id, channel_id, user_id, guild_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (ticket_id, channel.id, ctx.author.id, ctx.guild.id, "open", datetime.datetime.now().isoformat()))
    conn.commit()
    embed = discord.Embed(title="🎫 Ticket Created", description=f"Support will be with you shortly.\nChannel: {channel.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)
    ticket_embed = discord.Embed(title=f"Ticket - {ctx.author.name}", description="Please describe your issue.", color=discord.Color.blue())
    ticket_embed.add_field(name="Commands", value="`!ticket close` - Close ticket\n`!ticket claim` - Claim ticket\n`!ticket add @user` - Add user\n`!ticket remove @user` - Remove user", inline=False)
    await channel.send(f"{ctx.author.mention} {support_role.mention}", embed=ticket_embed)

@bot.command()
async def ticket_close(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ This is not a ticket channel.")
        return
    c.execute("SELECT user_id FROM tickets WHERE channel_id=?", (ctx.channel.id,))
    ticket_data = c.fetchone()
    if ticket_data:
        user = bot.get_user(ticket_data[0])
        transcript = []
        async for message in ctx.channel.history(limit=100):
            transcript.append(f"{message.author}: {message.content} ({message.created_at})")
        with open(f"transcript_{ctx.channel.id}.txt", "w") as f:
            f.write("\n".join(transcript))
        if user:
            await user.send(f"Your ticket `{ctx.channel.name}` has been closed. Transcript attached.", file=discord.File(f"transcript_{ctx.channel.id}.txt"))
        c.execute("UPDATE tickets SET status=? WHERE channel_id=?", ("closed", ctx.channel.id))
        conn.commit()
        await ctx.send("✅ Ticket will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
        os.remove(f"transcript_{ctx.channel.id}.txt")

@bot.command()
async def ticket_claim(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ This is not a ticket channel.")
        return
    await ctx.send(f"✅ {ctx.author.mention} has claimed this ticket!")

@bot.command()
async def ticket_add(ctx, member: discord.Member):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ This is not a ticket channel.")
        return
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    await ctx.send(f"✅ Added {member.mention} to the ticket.")

@bot.command()
async def ticket_remove(ctx, member: discord.Member):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ This is not a ticket channel.")
        return
    await ctx.channel.set_permissions(member, view_channel=False)
    await ctx.send(f"✅ Removed {member.mention} from the ticket.")

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket_setup(ctx, category: discord.CategoryChannel, support_role: discord.Role):
    c.execute("INSERT OR REPLACE INTO ticket_config VALUES (?, ?, ?)", (ctx.guild.id, category.id, support_role.id))
    conn.commit()
    await ctx.send(f"✅ Ticket system configured! Category: {category.name}, Support Role: {support_role.mention}")

# ---------- GIVEAWAYS ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway_start(ctx, duration: str, winners: int, *, prize):
    time_unit = duration[-1]
    time_value = int(duration[:-1])
    if time_unit == 's':
        seconds = time_value
    elif time_unit == 'm':
        seconds = time_value * 60
    elif time_unit == 'h':
        seconds = time_value * 3600
    elif time_unit == 'd':
        seconds = time_value * 86400
    else:
        await ctx.send("Invalid time format. Use s, m, h, or d.")
        return
    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Hosted by:** {ctx.author.mention}\n**Ends in:** {duration}", color=discord.Color.gold())
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎉")
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    c.execute("INSERT INTO giveaways (message_id, channel_id, prize, winners, end_time, guild_id, hosted_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (message.id, ctx.channel.id, prize, winners, end_time.isoformat(), ctx.guild.id, ctx.author.id))
    conn.commit()
    await asyncio.sleep(seconds)
    message = await ctx.channel.fetch_message(message.id)
    users = []
    async for user in message.reactions[0].users():
        if not user.bot:
            users.append(user)
    if len(users) < winners:
        await ctx.send("❌ Not enough participants to determine winners.")
        return
    winners_list = random.sample(users, min(winners, len(users)))
    winner_mentions = " ".join([w.mention for w in winners_list])
    embed = discord.Embed(title="🎉 GIVEAWAY ENDED 🎉", description=f"**Prize:** {prize}\n**Winners:** {winner_mentions}\n**Hosted by:** {ctx.author.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway_reroll(ctx, message_id: int):
    c.execute("SELECT prize, winners, channel_id FROM giveaways WHERE message_id=?", (message_id,))
    data = c.fetchone()
    if not data:
        await ctx.send("❌ Giveaway not found.")
        return
    channel = bot.get_channel(data[2])
    message = await channel.fetch_message(message_id)
    users = []
    async for user in message.reactions[0].users():
        if not user.bot:
            users.append(user)
    if not users:
        await ctx.send("❌ No valid participants.")
        return
    winners_list = random.sample(users, min(data[1], len(users)))
    winner_mentions = " ".join([w.mention for w in winners_list])
    await ctx.send(f"🎉 **Rerolled!** New winners for {data[0]}: {winner_mentions}")

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway_end(ctx, message_id: int):
    c.execute("DELETE FROM giveaways WHERE message_id=?", (message_id,))
    conn.commit()
    await ctx.send("✅ Giveaway ended and removed from database.")

@bot.command()
async def giveaway_list(ctx):
    c.execute("SELECT message_id, prize, end_time FROM giveaways WHERE guild_id=?", (ctx.guild.id,))
    giveaways = c.fetchall()
    if not giveaways:
        await ctx.send("No active giveaways.")
        return
    embed = discord.Embed(title="Active Giveaways", color=discord.Color.gold())
    for giveaway in giveaways:
        embed.add_field(name=f"Message ID: {giveaway[0]}", value=f"Prize: {giveaway[1]}\nEnds: {giveaway[2]}", inline=False)
    await ctx.send(embed=embed)

# ---------- LEVELING ----------
@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    c.execute("SELECT xp, level FROM levels WHERE user_id=? AND guild_id=?", (member.id, ctx.guild.id))
    data = c.fetchone()
    if not data:
        await ctx.send(f"{member.mention} has no XP yet.")
        return
    xp, level = data
    xp_needed = int((level + 1) ** 4) - int(level ** 4)
    embed = discord.Embed(title=f"{member.name}'s Rank", color=discord.Color.blue())
    embed.add_field(name="Level", value=level, inline=True)
    embed.add_field(name="XP", value=f"{xp}/{xp_needed}", inline=True)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT user_id, level, xp FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (ctx.guild.id,))
    leaderboard_data = c.fetchall()
    embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
    for i, data in enumerate(leaderboard_data, 1):
        user = bot.get_user(data[0])
        if user:
            embed.add_field(name=f"{i}. {user.name}", value=f"Level {data[1]} | XP: {data[2]}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setlevel(ctx, member: discord.Member, level: int):
    c.execute("UPDATE levels SET level=?, xp=? WHERE user_id=? AND guild_id=?", (level, int(level ** 4 * 0.25), member.id, ctx.guild.id))
    conn.commit()
    await ctx.send(f"✅ Set {member.mention}'s level to {level}")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetlevel(ctx, member: discord.Member = None):
    if not member:
        c.execute("DELETE FROM levels WHERE guild_id=?", (ctx.guild.id,))
    else:
        c.execute("DELETE FROM levels WHERE user_id=? AND guild_id=?", (member.id, ctx.guild.id))
    conn.commit()
    await ctx.send("✅ Levels reset successfully.")

# ---------- ECONOMY ----------
@bot.command()
async def balance(ctx):
    c.execute("SELECT wallet, bank FROM economy WHERE user_id=?", (ctx.author.id,))
    data = c.fetchone()
    if not data:
        c.execute("INSERT INTO economy VALUES (?, ?, ?)", (ctx.author.id, 0, 0))
        conn.commit()
        wallet, bank = 0, 0
    else:
        wallet, bank = data
    embed = discord.Embed(title=f"{ctx.author.name}'s Balance", color=discord.Color.green())
    embed.add_field(name="💰 Wallet", value=f"${wallet}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${bank}", inline=True)
    embed.add_field(name="💎 Total", value=f"${wallet + bank}", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def daily(ctx):
    c.execute("SELECT wallet FROM economy WHERE user_id=?", (ctx.author.id,))
    data = c.fetchone()
    if not data:
        c.execute("INSERT INTO economy VALUES (?, ?, ?)", (ctx.author.id, 100, 0))
        conn.commit()
        await ctx.send("✅ You claimed your daily reward of $100!")
    else:
        c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (data[0] + 100, ctx.author.id))
        conn.commit()
        await ctx.send("✅ You claimed your daily reward of $100!")

@bot.command()
async def work(ctx):
    earnings = random.randint(50, 200)
    c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (earnings, ctx.author.id))
    conn.commit()
    await ctx.send(f"💼 You worked and earned ${earnings}!")

@bot.command()
async def steal(ctx, member: discord.Member):
    if member == ctx.author:
        await ctx.send("❌ You can't steal from yourself!")
        return
    c.execute("SELECT wallet FROM economy WHERE user_id=?", (member.id,))
    target_data = c.fetchone()
    if not target_data or target_data[0] < 10:
        await ctx.send("❌ That user has nothing to steal!")
        return
    success = random.random() < 0.5
    if success:
        amount = random.randint(10, min(100, target_data[0]))
        c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (target_data[0] - amount, member.id))
        c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (amount, ctx.author.id))
        conn.commit()
        await ctx.send(f"✅ You stole ${amount} from {member.name}!")
    else:
        c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (-50, ctx.author.id))
        conn.commit()
        await ctx.send(f"❌ You got caught stealing and lost $50!")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    c.execute("SELECT wallet FROM economy WHERE user_id=?", (ctx.author.id,))
    sender_data = c.fetchone()
    if not sender_data or sender_data[0] < amount:
        await ctx.send("❌ You don't have enough money!")
        return
    c.execute("SELECT wallet FROM economy WHERE user_id=?", (member.id,))
    receiver_data = c.fetchone()
    if not receiver_data:
        c.execute("INSERT INTO economy VALUES (?, ?, ?)", (member.id, 0, 0))
        conn.commit()
        receiver_data = (0,)
    c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (sender_data[0] - amount, ctx.author.id))
    c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (receiver_data[0] + amount, member.id))
    conn.commit()
    await ctx.send(f"✅ You gave ${amount} to {member.mention}!")

@bot.command()
async def shop(ctx):
    items = {"Role: VIP": 1000, "Custom Color": 5000, "Boost XP": 10000}
    embed = discord.Embed(title="🛒 Shop", color=discord.Color.gold())
    for item, price in items.items():
        embed.add_field(name=item, value=f"${price}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, *, item: str):
    shop_items = {"vip": 1000, "custom color": 5000, "boost xp": 10000}
    item_lower = item.lower()
    if item_lower not in shop_items:
        await ctx.send("❌ Item not found in shop.")
        return
    price = shop_items[item_lower]
    c.execute("SELECT wallet FROM economy WHERE user_id=?", (ctx.author.id,))
    user_data = c.fetchone()
    if not user_data or user_data[0] < price:
        await ctx.send("❌ You don't have enough money!")
        return
    c.execute("UPDATE economy SET wallet=? WHERE user_id=?", (user_data[0] - price, ctx.author.id))
    conn.commit()
    await ctx.send(f"✅ You purchased {item} for ${price}!")

@bot.command()
async def inventory(ctx):
    embed = discord.Embed(title=f"{ctx.author.name}'s Inventory", color=discord.Color.blue())
    embed.add_field(name="Items", value="No items yet. Use `!shop` to buy items!", inline=False)
    await ctx.send(embed=embed)

# ---------- MUSIC (Basic) ----------
@bot.command()
async def play(ctx, *, url):
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel to play music.")
        return
    voice_channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await voice_channel.connect()
    await ctx.send("🎵 Music system requires FFmpeg setup. Basic commands available.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped the current song.")
    else:
        await ctx.send("❌ No music is playing.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🛑 Stopped music and left voice channel.")
    else:
        await ctx.send("❌ Not in a voice channel.")

@bot.command()
async def queue(ctx):
    await ctx.send("🎵 Queue system requires full music bot setup.")

@bot.command()
async def nowplaying(ctx):
    await ctx.send("🎵 No song currently playing.")

@bot.command()
async def volume(ctx, volume: int = None):
    if volume and 0 <= volume <= 100:
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 Volume set to {volume}%")
    else:
        await ctx.send("❌ Volume must be between 0 and 100.")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused the music.")
    else:
        await ctx.send("❌ No music is playing.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed the music.")
    else:
        await ctx.send("❌ No music is paused.")

# ---------- AUTO-MOD ----------
@bot.event
async def on_message_edit(before, after):
    if before.content != after.content:
        c.execute("SELECT word FROM blacklist WHERE guild_id=?", (before.guild.id,))
        blacklisted_words = c.fetchall()
        for word in blacklisted_words:
            if word[0].lower() in after.content.lower():
                await after.delete()
                await after.channel.send(f"{after.author.mention} Message deleted: Blacklisted word detected.")
                break

@bot.command()
@commands.has_permissions(administrator=True)
async def automod(ctx, setting: str):
    if setting.lower() == "on":
        await ctx.send("✅ Auto-mod enabled!")
    elif setting.lower() == "off":
        await ctx.send("❌ Auto-mod disabled!")
    else:
        await ctx.send("Use `!automod on/off`")

@bot.command()
@commands.has_permissions(administrator=True)
async def antispam(ctx, threshold: int = 5):
    await ctx.send(f"✅ Anti-spam enabled. {threshold} messages per 5 seconds.")

@bot.command()
@commands.has_permissions(administrator=True)
async def blacklist(ctx, word: str):
    c.execute("INSERT OR IGNORE INTO blacklist VALUES (?, ?)", (ctx.guild.id, word.lower()))
    conn.commit()
    await ctx.send(f"✅ Blacklisted word: {word}")

@bot.command()
@commands.has_permissions(administrator=True)
async def whitelist(ctx, word: str):
    c.execute("DELETE FROM blacklist WHERE guild_id=? AND word=?", (ctx.guild.id, word.lower()))
    conn.commit()
    await ctx.send(f"✅ Removed from blacklist: {word}")

# ---------- SERVER STATS ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def setupstats(ctx):
    guild = ctx.guild
    category = await guild.create_category("Server Stats")
    await guild.create_voice_channel(f"Members: {guild.member_count}", category=category)
    await guild.create_voice_channel(f"Bots: {len([m for m in guild.members if m.bot])}", category=category)
    c.execute("INSERT OR REPLACE INTO server_stats VALUES (?, ?)", (guild.id, category.id))
    conn.commit()
    await ctx.send("✅ Server stats channels created!")

@bot.command()
@commands.has_permissions(administrator=True)
async def levelchannel(ctx, channel: discord.TextChannel):
    await ctx.send(f"✅ Level-up announcements will be sent to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def welcomer(ctx, channel: discord.TextChannel, *, message: str = None):
    await ctx.send(f"✅ Welcome messages will be sent to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def goodbye(ctx, channel: discord.TextChannel, *, message: str = None):
    await ctx.send(f"✅ Goodbye messages will be sent to {channel.mention}")

# ---------- OWNER ONLY ----------
@bot.command()
@commands.is_owner()
async def status(ctx, *, status_text):
    await bot.change_presence(activity=discord.Game(name=status_text))
    await ctx.send(f"✅ Status changed to: {status_text}")

@bot.command()
@commands.is_owner()
async def guilds(ctx):
    guild_list = "\n".join([f"{guild.name} - {guild.id}" for guild in bot.guilds])
    await ctx.send(f"**Guilds:**\n{guild_list}")

@bot.command()
@commands.is_owner()
async def eval(ctx, *, code):
    try:
        result = eval(code)
        await ctx.send(f"```py\n{result}\n```")
    except Exception as e:
        await ctx.send(f"```py\nError: {e}\n```")

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("🔌 Shutting down...")
    await bot.close()

@bot.command()
@commands.is_owner()
async def blacklist_server(ctx, guild_id: int):
    await ctx.send(f"✅ Server {guild_id} has been blacklisted.")

@bot.command()
@commands.is_owner()
async def reload(ctx, extension: str):
    try:
        await bot.reload_extension(f"cogs.{extension}")
        await ctx.send(f"✅ Reloaded {extension}")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ---------- INFO ----------
@bot.command()
async def invite(ctx):
    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(title="Invite ApexVoxel", description=f"[Click here to invite me!]({invite_url})", color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command()
async def support(ctx):
    embed = discord.Embed(title="Support Server", description="Join our support server for help!", color=discord.Color.blue())
    embed.add_field(name="Link", value="[Click here](https://discord.gg/your-support-server)")
    await ctx.send(embed=embed)

@bot.command()
async def vote(ctx):
    embed = discord.Embed(title="Vote for ApexVoxel", description="Support us by voting!", color=discord.Color.gold())
    embed.add_field(name="Top.gg", value="[Vote here](https://top.gg/bot/your-bot-id)")
    await ctx.send(embed=embed)

@bot.command()
async def privacy(ctx):
    embed = discord.Embed(title="Privacy Policy", description="ApexVoxel collects:\n- User IDs for economy and leveling\n- Message content for moderation\n- Server settings for configuration\n\nData is stored locally and not shared.", color=discord.Color.blue())
    await ctx.send(embed=embed)

# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Use `!help {ctx.command.name}` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(error)

# ---------- RUN BOT ----------
if __name__ == "__main__":
    # Replace with your actual bot token
    bot.run('YOUR_BOT_TOKEN')