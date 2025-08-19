import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
import json
import os
from flask import Flask
from threading import Thread

# ------------------------
# Keep-alive (for Replit/uptime pings)
# ------------------------
app = Flask('')


@app.route('/')
def home():
    return "Bot is running!"


def _run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    Thread(target=_run, daemon=True).start()


# ------------------------
# Bot configuration
# ------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "players.json"

# Specializations (aliases + detailed info)
SPECIALIZATIONS = {
    "Weapons Masters": {
        "aliases": ["weapons", "weapon", "wep"],
        "info": (
            "- Can skillfully make **Swords, Bows, Axes, Maces, Staffs, and Shields**.\n "
            "- When crafting these items, the recipe is treated as if it had **one additional star**.\n"
            "- If the recipe is at **five stars**, the Weapon Master has a chance to produce **Epic gear**.\n "
            "- Crafted weapons have stats comparable to dropped weapons.\n"
        )
    },
    "Armor Masters": {
        "aliases": ["armor", "armour"],
        "info": (
            "- Can skillfully make **Chest Armor, Gloves, Boots, Belts, and Helms**.\n"
            "- When crafting any armor, their recipe is treated as if it had **one additional star**.\n "
            "- If the recipe is at **five stars**, the Armor Master has a chance to produce **Epic gear**.\n"
        )
    },
    "Potions Masters": {
        "aliases": ["potions", "potion"],
        "info": (
            "- Skilled cooks who create Potions and Drams with a chance to gain between **1 and 4 extra potions or drams** per craft without extra ingredients.\n "
            "- Only they can make **Treasure Drams** (significantly increase Magic Find) and **Malice Drams** (increase both Savagery and Brutality).\n "
            " **Note:** Bonus potions may be lost if crafting with a full backpack, so free inventory slots are advised.\n"
        )
    },
    "Preparations Masters": {
        "aliases": ["preparations", "prep"],
        "info": (
            "- Skilled at creating preparation items.\n "
            "- When crafting, the **gold cost is waived** (totally free), but the master must have the gold initially.\n "
            "- They can make three unique preparations that only they can make: **Wood Pitch** (increases Onslaught on feet), **Mineral Oils** (increase Blasting on helms), and **Leather Stitching** (increases Poise on belts).\n"
        )
    },
    "Production Masters": {
        "aliases": ["production", "prod"],
        "info": (
            "- Skilled with **Motes of Yorick**. Have a bonus **5% Mote Reduction** chance, returning **all motes** when triggered instead of half.\n "
            "- Earn **50% more crafting experience**."
        )
    },
}



# ------------------------
# Persistence helpers (per-guild storage)
# players_data structure:
# {
#   "<guild_id_str>": {
#       "Weapons Masters": [...],
#       "Armor Masters": [...],
#       ...
#   },
#   ...
# }
# ------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


players_data = load_data()


def ensure_guild_init(guild_id: int):
    gid = str(guild_id)
    if gid not in players_data:
        players_data[gid] = {spec: [] for spec in SPECIALIZATIONS.keys()}
        save_data(players_data)
    else:
        # If code was updated with new specs, ensure keys exist
        changed = False
        for spec in SPECIALIZATIONS.keys():
            if spec not in players_data[gid]:
                players_data[gid][spec] = []
                changed = True
        if changed:
            save_data(players_data)


def get_spec_name(alias: str):
    alias = alias.strip().lower()
    for spec, data in SPECIALIZATIONS.items():
        if alias == spec.lower() or alias in data["aliases"]:
            return spec
    return None


# ------------------------
# Persistent Dropdown UI (/menu)
# ------------------------
class SpecializationDropdown(Select):

    def __init__(self):
        options = [
            discord.SelectOption(label=spec,
                                 description=(data["info"].replace("**",
                                                                   ""))[:80])
            for spec, data in SPECIALIZATIONS.items()
        ]
        super().__init__(
            placeholder="Select a Specialization",
            options=options,
            custom_id="specialization_dropdown"  # required for persistence
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This can only be used in a server.", ephemeral=True)
            return
        ensure_guild_init(interaction.guild.id)
        gid = str(interaction.guild.id)
        spec = self.values[0]
        names = players_data[gid].get(spec, [])
        # Paginate via a helper view if long
        await send_paginated_names(interaction, spec, names, ephemeral=True)


class SpecializationView(View):

    def __init__(self):
        super().__init__(timeout=None)  # persistent
        self.add_item(SpecializationDropdown())


# ------------------------
# Pagination View
# ------------------------
class PaginationView(View):

    def __init__(self, embeds, owner: discord.abc.User):
        super().__init__(timeout=90)
        self.embeds = embeds
        self.owner = owner
        self.idx = 0

        self.prev_btn = Button(label="⬅ Previous",
                               style=discord.ButtonStyle.secondary)
        self.next_btn = Button(label="Next ➡",
                               style=discord.ButtonStyle.secondary)

        self.prev_btn.callback = self.prev_page
        self.next_btn.callback = self.next_page

        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self._update_state()

    def _update_state(self):
        self.prev_btn.disabled = (self.idx <= 0)
        self.next_btn.disabled = (self.idx >= len(self.embeds) - 1)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "You can’t control this pagination.", ephemeral=True)
            return
        if self.idx > 0:
            self.idx -= 1
            self._update_state()
        await interaction.response.edit_message(embed=self.embeds[self.idx],
                                                view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "You can’t control this pagination.", ephemeral=True)
            return
        if self.idx < len(self.embeds) - 1:
            self.idx += 1
            self._update_state()
        await interaction.response.edit_message(embed=self.embeds[self.idx],
                                                view=self)


# Helper to send paginated names list
async def send_paginated_names(interaction: discord.Interaction,
                               spec_name: str,
                               names: list[str],
                               ephemeral: bool = True):
    if not names:
        await interaction.response.send_message(
            f"_No players found for **{spec_name}**._", ephemeral=ephemeral)
        return

    chunk_size = 20
    chunks = [
        names[i:i + chunk_size] for i in range(0, len(names), chunk_size)
    ]
    embeds = []
    for i, chunk in enumerate(chunks, start=1):
        embed = discord.Embed(
            title=f"{spec_name} — Players (Page {i}/{len(chunks)})",
            description=", ".join(chunk),
            color=discord.Color.blurple())
        embeds.append(embed)

    if len(embeds) == 1:
        await interaction.response.send_message(embed=embeds[0],
                                                ephemeral=ephemeral)
    else:
        view = PaginationView(embeds, interaction.user)
        await interaction.response.send_message(embed=embeds[0],
                                                view=view,
                                                ephemeral=ephemeral)


# ------------------------
# Slash commands
# ------------------------
@bot.event
async def on_ready():
    # Register persistent view (for messages already using this view)
    bot.add_view(SpecializationView())
    # Register slash commands globally
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Slash sync error: {e}")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


# Autocomplete for specialization (includes aliases)
async def specialization_autocomplete(interaction: discord.Interaction,
                                      current: str):
    q = (current or "").lower()
    seen = set()
    results = []
    # Canonical names first
    for spec in SPECIALIZATIONS.keys():
        if q in spec.lower():
            results.append(spec)
            seen.add(spec)
    # Then alias matches
    for spec, data in SPECIALIZATIONS.items():
        if spec in seen:  # already added
            continue
        if any(q in alias for alias in data["aliases"]):
            results.append(spec)
    return [
        app_commands.Choice(name=spec, value=spec) for spec in results[:25]
    ]


# /menu — show persistent dropdown
@bot.tree.command(
    name="menu",
    description="Show the specialization selection menu (dropdown).")
async def menu(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "This can only be used in a server.", ephemeral=True)
        return
    ensure_guild_init(interaction.guild.id)
    await interaction.response.send_message("Choose a specialization:",
                                            view=SpecializationView(),
                                            ephemeral=True)


# /help — rich help
@bot.tree.command(name="help", description="Show all available commands.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Villagers & Heroes — Bot Help",
                          color=discord.Color.green())
    embed.add_field(name="/menu",
                    value="Show specialization dropdown menu (browse via UI).",
                    inline=False)
    embed.add_field(name="/help",
                    value="Show this help message.",
                    inline=False)
    embed.add_field(name="/specializations",
                    value="Show detailed specialization info.",
                    inline=False)
    embed.add_field(
        name="/list",
        value="List players for a specialization (with pagination).",
        inline=False)
    embed.add_field(
        name="/all_players",
        value="Show all players across all specializations (this server).",
        inline=False)
    embed.add_field(name="/add",
                    value="(Admin only) Add players to a specialization.",
                    inline=False)
    embed.add_field(name="/remove",
                    value="(Admin only) Remove players from a specialization.",
                    inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# /specializations — detailed descriptions
@bot.tree.command(name="specializations",
                  description="Show detailed specialization information.")
async def specializations_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Specializations — Details",
                          color=discord.Color.gold())
    for spec, data in SPECIALIZATIONS.items():
        embed.add_field(name=spec, value=data["info"], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# /add — Admin only
@bot.tree.command(name="add",
                  description="(Admin only) Add players to a specialization.")
@app_commands.describe(specialization="Specialization",
                       names="Comma-separated player names")
@app_commands.autocomplete(specialization=specialization_autocomplete)
async def add_cmd(interaction: discord.Interaction, specialization: str,
                  names: str):
    if not interaction.guild:
        await interaction.response.send_message(
            "This can only be used in a server.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You must be an Admin to use this command.", ephemeral=True)
        return

    ensure_guild_init(interaction.guild.id)
    gid = str(interaction.guild.id)
    spec_name = get_spec_name(specialization)
    if not spec_name:
        await interaction.response.send_message("❌ Invalid specialization.",
                                                ephemeral=True)
        return

    names_list = [n.strip() for n in names.split(",") if n.strip()]
    added = []
    for n in names_list:
        if n not in players_data[gid][spec_name]:
            players_data[gid][spec_name].append(n)
            added.append(n)
    save_data(players_data)

    msg = f"✅ Added **{', '.join(added)}** to **{spec_name}**." if added else "ℹ No new names were added."
    await interaction.response.send_message(msg, ephemeral=True)


# /remove — Admin only
@bot.tree.command(
    name="remove",
    description="(Admin only) Remove players from a specialization.")
@app_commands.describe(specialization="Specialization",
                       names="Comma-separated player names")
@app_commands.autocomplete(specialization=specialization_autocomplete)
async def remove_cmd(interaction: discord.Interaction, specialization: str,
                     names: str):
    if not interaction.guild:
        await interaction.response.send_message(
            "This can only be used in a server.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You must be an Admin to use this command.", ephemeral=True)
        return

    ensure_guild_init(interaction.guild.id)
    gid = str(interaction.guild.id)
    spec_name = get_spec_name(specialization)
    if not spec_name:
        await interaction.response.send_message("❌ Invalid specialization.",
                                                ephemeral=True)
        return

    names_list = [n.strip() for n in names.split(",") if n.strip()]
    removed = []
    for n in names_list:
        if n in players_data[gid][spec_name]:
            players_data[gid][spec_name].remove(n)
            removed.append(n)
    save_data(players_data)

    msg = f"🗑 Removed **{', '.join(removed)}** from **{spec_name}**." if removed else "ℹ None of those names were in the list."
    await interaction.response.send_message(msg, ephemeral=True)


# /list — with pagination
@bot.tree.command(
    name="list",
    description="List players for a specialization (this server).")
@app_commands.describe(specialization="Specialization")
@app_commands.autocomplete(specialization=specialization_autocomplete)
async def list_cmd(interaction: discord.Interaction, specialization: str):
    if not interaction.guild:
        await interaction.response.send_message(
            "This can only be used in a server.", ephemeral=True)
        return

    ensure_guild_init(interaction.guild.id)
    gid = str(interaction.guild.id)
    spec_name = get_spec_name(specialization)
    if not spec_name:
        await interaction.response.send_message("❌ Invalid specialization.",
                                                ephemeral=True)
        return

    names = players_data[gid].get(spec_name, [])
    await send_paginated_names(interaction, spec_name, names, ephemeral=True)


# /all_players — per server only
@bot.tree.command(
    name="all_players",
    description=
    "Show all players across all specializations (this server only).")
async def all_players_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "This can only be used in a server.", ephemeral=True)
        return

    ensure_guild_init(interaction.guild.id)
    gid = str(interaction.guild.id)

    embed = discord.Embed(title="All Players — This Server",
                          color=discord.Color.green())
    empty = True
    for spec in SPECIALIZATIONS.keys():
        names = players_data[gid].get(spec, [])
        if names:
            empty = False
        embed.add_field(name=spec,
                        value=", ".join(names) if names else "_None_",
                        inline=False)

    if empty:
        await interaction.response.send_message(
            "_No players found in this server yet._", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ------------------------
# Run
# ------------------------
keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN is not set.")
bot.run(TOKEN)




