import discord
from discord.ext import commands
import json
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = 'players.json'

SPECIALIZATIONS = {
    "weapon": "Weapons Masters",
    "armor": "Armor Masters",
    "potion": "Potions Masters",
    "preparation": "Preparations Masters",
    "production": "Production Masters"
}

SPECIALIZATION_INFO = {
    "Weapons Masters": "Chance to craft weapons with Epic stats; recipe mastery acts as if you have an extra rank/star.",
    "Armor Masters": "Chance to craft armor with Epic stats; recipe mastery acts as if you have an extra rank/star.",
    "Potions Masters": "Can create Treasure Drams and Malice Drams; chance to create 1-4 extra items.",
    "Preparations Masters": "Can create Preparations for gear; zero gold crafting cost.",
    "Production Masters": "Mote reduction; 50% more experience while crafting."
}

def load_data():
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

players = load_data()

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

@bot.command()
@commands.check(is_admin)
async def add(ctx, specialization: str, *, names: str):
    spec_key = specialization.lower()
    if spec_key not in SPECIALIZATIONS:
        await ctx.send("Invalid specialization. Use `!specializations info` to see valid options.")
        return

    spec_full = SPECIALIZATIONS[spec_key]
    name_list = [n.strip() for n in names.split(",")]
    for name in name_list:
        players[name] = spec_full
    save_data(players)
    await ctx.send(f"Added {', '.join(name_list)} as {spec_full}.")

@bot.command()
@commands.check(is_admin)
async def remove(ctx, *, names: str):
    name_list = [n.strip() for n in names.split(",")]
    removed = []
    for name in name_list:
        if name in players:
            del players[name]
            removed.append(name)
    save_data(players)
    if removed:
        await ctx.send(f"Removed: {', '.join(removed)}")
    else:
        await ctx.send("No matching players found.")

@bot.command()
async def list(ctx, specialization: str):
    spec_key = specialization.lower()
    if spec_key not in SPECIALIZATIONS:
        await ctx.send("Invalid specialization. Use `!specializations info` to see valid options.")
        return

    spec_full = SPECIALIZATIONS[spec_key]
    matches = [n for n, s in players.items() if s == spec_full]
    if matches:
        await ctx.send(f"**{spec_full}:** {', '.join(matches)}")
    else:
        await ctx.send(f"No players with specialization **{spec_full}** found.")

@bot.command(naimport discord
from discord.ext import commands
import json
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = 'players.json'

SPECIALIZATIONS = {
    "weapon": "Weapons Masters",
    "armor": "Armor Masters",
    "potion": "Potions Masters",
    "preparation": "Preparations Masters",
    "production": "Production Masters"
}

SPECIALIZATION_INFO = {
    "Weapons Masters": "Chance to craft weapons with Epic stats; recipe mastery acts as if you have an extra rank/star.",
    "Armor Masters": "Chance to craft armor with Epic stats; recipe mastery acts as if you have an extra rank/star.",
    "Potions Masters": "Can create Treasure Drams and Malice Drams; chance to create 1-4 extra items.",
    "Preparations Masters": "Can create Preparations for gear; zero gold crafting cost.",
    "Production Masters": "Mote reduction; 50% more experience while crafting."
}

def load_data():
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

players = load_data()

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

@bot.command()
@commands.check(is_admin)
async def add(ctx, specialization: str, *, names: str):
    spec_key = specialization.lower()
    if spec_key not in SPECIALIZATIONS:
        await ctx.send("Invalid specialization. Use `!specializations info` to see valid options.")
        return

    spec_full = SPECIALIZATIONS[spec_key]
    name_list = [n.strip() for n in names.split(",")]
    for name in name_list:
        players[name] = spec_full
    save_data(players)
    await ctx.send(f"Added {', '.join(name_list)} as {spec_full}.")

@bot.command()
@commands.check(is_admin)
async def remove(ctx, *, names: str):
    name_list = [n.strip() for n in names.split(",")]
    removed = []
    for name in name_list:
        if name in players:
            del players[name]
            removed.append(name)
    save_data(players)
    if removed:
        await ctx.send(f"Removed: {', '.join(removed)}")
    else:
        await ctx.send("No matching players found.")

@bot.command()
async def list(ctx, specialization: str):
    spec_key = specialization.lower()
    if spec_key not in SPECIALIZATIONS:
        await ctx.send("Invalid specialization. Use `!specializations info` to see valid options.")
        return

    spec_full = SPECIALIZATIONS[spec_key]
    matches = [n for n, s in players.items() if s == spec_full]
    if matches:
        await ctx.send(f"**{spec_full}:** {', '.join(matches)}")
    else:
        await ctx.send(f"No players with specialization **{spec_full}** found.")

@bot.command(name="specializations")
async def specializations_info(ctx):
    embed = discord.Embed(title="Crafting Specializations Info", color=0x00ff00)
    for spec, info in SPECIALIZATION_INFO.items():
        embed.add_field(name=spec, value=info, inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Bot Commands", color=0x3498db)
    embed.add_field(name="!add <specialization> <name1>, <name2>, ...",
                    value="Add players under a specialization (Admin only). Example: `!add weapon Alice, Bob`",
                    inline=False)
    embed.add_field(name="!remove <name1>, <name2>, ...",
                    value="Remove players (Admin only). Example: `!remove Alice, Bob`",
                    inline=False)
    embed.add_field(name="!list <specialization>",
                    value="List all players under a specialization. Example: `!list weapon`",
                    inline=False)
    embed.add_field(name="!specializations info",
                    value="Show all specializations and their details.",
                    inline=False)
    await ctx.send(embed=embed)

@add.error
@remove.error
async def admin_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Only server admins can use this command.")

bot.run('YOUR_BOT_TOKEN')
me="specializations")
async def specializations_info(ctx):
    embed = discord.Embed(title="Crafting Specializations Info", color=0x00ff00)
    for spec, info in SPECIALIZATION_INFO.items():
        embed.add_field(name=spec, value=info, inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Bot Commands", color=0x3498db)
    embed.add_field(name="!add <specialization> <name1>, <name2>, ...",
                    value="Add players under a specialization (Admin only). Example: `!add weapon Alice, Bob`",
                    inline=False)
    embed.add_field(name="!remove <name1>, <name2>, ...",
                    value="Remove players (Admin only). Example: `!remove Alice, Bob`",
                    inline=False)
    embed.add_field(name="!list <specialization>",
                    value="List all players under a specialization. Example: `!list weapon`",
                    inline=False)
    embed.add_field(name="!specializations info",
                    value="Show all specializations and their details.",
                    inline=False)
    await ctx.send(embed=embed)

@add.error
@remove.error
async def admin_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Only server admins can use this command.")

bot.run('YOUR_BOT_TOKEN')
