import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Modal, TextInput, Button
import os
from flask import Flask
from threading import Thread
import psycopg2
import urllib.parse as up
import asyncio
from datetime import datetime, timedelta
from discord import  Interaction, TextChannel, Role, SelectOption, Embed, Color


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

# ------------------------
# PostgreSQL Persistence
# ------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in Render environment.")

up.uses_netloc.append("postgres")
url = up.urlparse(DATABASE_URL)


def get_conn():
    return psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            guild_id TEXT NOT NULL,
            specialization TEXT NOT NULL,
            player_name TEXT NOT NULL,
            PRIMARY KEY (guild_id, specialization, player_name)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


init_db()


def load_data():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT guild_id, specialization, player_name FROM players")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    data = {}
    for guild_id, specialization, player_name in rows:
        if guild_id not in data:
            data[guild_id] = {spec: [] for spec in SPECIALIZATIONS.keys()}
        if specialization not in data[guild_id]:
            data[guild_id][specialization] = []
        data[guild_id][specialization].append(player_name)
    return data


def save_data(data, guild_id=None, specialization=None, add=None, remove=None):
    """
    Incremental updates:
    - add: list of names to add
    - remove: list of names to remove
    If no args provided, rewrite all data (fallback, like JSON style)
    """
    conn = get_conn()
    cur = conn.cursor()

    if guild_id and specialization:
        if add:
            for name in add:
                cur.execute(
                    "INSERT INTO players (guild_id, specialization, player_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (guild_id, specialization, name)
                )
        if remove:
            for name in remove:
                cur.execute(
                    "DELETE FROM players WHERE guild_id=%s AND specialization=%s AND player_name=%s",
                    (guild_id, specialization, name)
                )
    else:
        # fallback: rewrite everything
        cur.execute("DELETE FROM players")
        for gid, specs in data.items():
            for spec, names in specs.items():
                for name in names:
                    cur.execute(
                        "INSERT INTO players (guild_id, specialization, player_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (gid, spec, name)
                    )
    conn.commit()
    cur.close()
    conn.close()


# ------------------------
# Reminder Feature Integration
# ------------------------

# ------------------------
# Database Table for Reminders
# ------------------------
def init_reminders_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            channel_id TEXT NOT NULL,
            role_id TEXT,
            location TEXT,
            interval TEXT NOT NULL,
            day_of_week TEXT,
            month_day TEXT,
            event_time TIMESTAMP NOT NULL,
            pre_reminder_minutes INT DEFAULT 5,
            enabled BOOLEAN DEFAULT TRUE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


init_reminders_db()

# ------------------------
# Reminder Helpers
# ------------------------
async def send_reminder(reminder, pre=False):
    guild = bot.get_guild(int(reminder['guild_id']))
    if not guild:
        return
    channel = guild.get_channel(int(reminder['channel_id']))
    if not channel:
        return

    embed = discord.Embed(
        title=f"{'⏳ Upcoming Event:' if pre else get_interval_emoji(reminder['interval']) + ' '}{reminder['name']}",
        description=f"{reminder['description'] or ''}\n"
                    f"{'Location: ' + reminder['location'] if reminder.get('location') else ''}"
                    f"{'' if pre else ''}",
        color=get_interval_color(reminder['interval'])
    )

    if pre:
        embed.title = f"⏳ Upcoming Event: {reminder['name']}"
        embed.description += f"\nStarting in {reminder['pre_reminder_minutes']} minutes!"
    
    msg_content = f"<@&{reminder['role_id']}>" if reminder.get('role_id') else None
    await channel.send(content=msg_content, embed=embed)

def get_interval_emoji(interval):
    return {
        "daily": "🔹",
        "weekly": "🟢",
        "monthly": "🟣",
        "one-time": "⚪"
    }.get(interval.lower(), "⚪")

def get_interval_color(interval):
    return {
        "daily": discord.Color.blue(),
        "weekly": discord.Color.green(),
        "monthly": discord.Color.purple(),
        "one-time": discord.Color.light_grey()
    }.get(interval.lower(), discord.Color.light_grey())

# Fetch all active reminders
def get_active_reminders():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reminders WHERE enabled=TRUE")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    reminders = []
    for row in rows:
        reminders.append({
            'id': row[0],
            'guild_id': row[1],
            'name': row[2],
            'description': row[3],
            'channel_id': row[4],
            'role_id': row[5],
            'location': row[6],
            'interval': row[7],
            'day_of_week': row[8],
            'month_day': row[9],
            'event_time': row[10],
            'pre_reminder_minutes': row[11],
            'enabled': row[12]
        })
    return reminders

# Add new reminder to DB
def add_reminder_to_db(data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reminders (
            guild_id, name, description, channel_id, role_id, location, interval,
            day_of_week, month_day, event_time, pre_reminder_minutes, enabled
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
    """, (
        data['guild_id'], data['name'], data.get('description'), data['channel_id'],
        data.get('role_id'), data.get('location'), data['interval'],
        data.get('day_of_week'), data.get('month_day'), data['event_time'],
        data.get('pre_reminder_minutes', 5)
    ))
    conn.commit()
    cur.close()
    conn.close()

# Remove reminder
def remove_reminder_from_db(reminder_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id=%s", (reminder_id,))
    conn.commit()
    cur.close()
    conn.close()

# Enable/disable reminder
def toggle_reminder_in_db(reminder_id, enable=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET enabled=%s WHERE id=%s", (enable, reminder_id))
    conn.commit()
    cur.close()
    conn.close()

# ------------------------
# Reminder Background Task
# ------------------------
async def reminder_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        reminders = get_active_reminders()
        for r in reminders:
            event_time = r['event_time']
            pre_time = event_time - timedelta(minutes=r.get('pre_reminder_minutes', 5))

            # Send pre-reminder
            if pre_time <= now < pre_time + timedelta(seconds=60):
                asyncio.create_task(send_reminder(r, pre=True))

            # Send main reminder
            if event_time <= now < event_time + timedelta(seconds=60):
                asyncio.create_task(send_reminder(r, pre=False))

                # Handle repeating events
                if r['interval'] == 'daily':
                    new_time = event_time + timedelta(days=1)
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE reminders SET event_time=%s WHERE id=%s", (new_time, r['id']))
                    conn.commit()
                    cur.close()
                    conn.close()
                elif r['interval'] == 'weekly':
                    new_time = event_time + timedelta(weeks=1)
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE reminders SET event_time=%s WHERE id=%s", (new_time, r['id']))
                    conn.commit()
                    cur.close()
                    conn.close()
                elif r['interval'] == 'monthly':
                    # rough approximation: add 30 days
                    new_time = event_time + timedelta(days=30)
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE reminders SET event_time=%s WHERE id=%s", (new_time, r['id']))
                    conn.commit()
                    cur.close()
                    conn.close()
                else:
                    # One-time, disable
                    toggle_reminder_in_db(r['id'], enable=False)

        await asyncio.sleep(30)  # check every 30 seconds

# bot.loop.create_task(reminder_loop())
@bot.event
async def on_ready():
    if not hasattr(bot, "reminder_task"):
        bot.reminder_task = asyncio.create_task(reminder_loop())

# ------------------------
# Slash Commands for Reminders
# ------------------------
@bot.tree.command(name="reminder_add", description="Add a new reminder (admin only).")
@app_commands.describe(
    name="Event name",
    description="Optional description",
    channel="Channel for reminder",
    time="Time of event (HH:MM or full datetime)",
    interval="Daily / Weekly / Monthly / One-time",
    role="Optional role to ping",
    pre_reminder="Minutes before event for pre-reminder",
    location="Optional location"
)
async def reminder_add(interaction: discord.Interaction, name:str, channel:discord.TextChannel,
                       time:str, interval:str, description:str=None, role:discord.Role=None,
                       pre_reminder:int=5, location:str=None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an Admin.", ephemeral=True)
        return
    # Parse time input
    try:
        if len(time.split(":")) == 2:
            today = datetime.utcnow().date()
            hours, minutes = map(int, time.split(":"))
            event_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)
        else:
            # full datetime
            event_time = datetime.fromisoformat(time)
    except Exception:
        await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)
        return

    reminder_data = {
        "guild_id": str(interaction.guild.id),
        "name": name,
        "description": description,
        "channel_id": str(channel.id),
        "role_id": str(role.id) if role else None,
        "location": location,
        "interval": interval.lower(),
        "event_time": event_time,
        "pre_reminder_minutes": pre_reminder
    }
    add_reminder_to_db(reminder_data)
    await interaction.response.send_message(f"✅ Reminder **{name}** added.", ephemeral=True)


@bot.tree.command(name="reminder_list", description="List all active reminders.")
async def reminder_list(interaction: discord.Interaction):
    reminders = get_active_reminders()
    reminders = [r for r in reminders if r['guild_id'] == str(interaction.guild.id)]
    if not reminders:
        await interaction.response.send_message("_No active reminders._", ephemeral=True)
        return

    embed = discord.Embed(title="Active Reminders", color=discord.Color.green())
    for r in reminders:
        embed.add_field(
            name=r['name'],
            value=f"Time: {r['event_time']}\n"
                  f"Channel: <#{r['channel_id']}>\n"
                  f"Role: <@&{r['role_id']}>\n"
                  f"Pre-reminder: {r['pre_reminder_minutes']} min",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="reminder_remove", description="Remove a reminder.")
@app_commands.describe(reminder_id="Reminder ID")
async def reminder_remove(interaction: discord.Interaction, reminder_id:int):
    remove_reminder_from_db(reminder_id)
    await interaction.response.send_message(f"✅ Reminder removed.", ephemeral=True)


@bot.tree.command(name="reminder_toggle", description="Enable/disable a reminder.")
@app_commands.describe(reminder_id="Reminder ID", enable="Enable or disable")
async def reminder_toggle(interaction: discord.Interaction, reminder_id:int, enable:bool):
    toggle_reminder_in_db(reminder_id, enable)
    await interaction.response.send_message(f"✅ Reminder {'enabled' if enable else 'disabled'}.", ephemeral=True)



# ------------------------
# Interactive Reminder Modal
# ------------------------

# ------------------------
# Reminder Modal (Add / Edit)
# ------------------------
class ReminderModal(Modal):
    def __init__(self, guild, channel=None, role=None, interval="one-time", reminder_data=None):
        """
        reminder_data: dict for editing existing reminder, None for new reminder
        """
        super().__init__(title="Reminder Setup")
        self.guild = guild
        self.channel = channel
        self.role = role
        self.interval = interval
        self.reminder_data = reminder_data  # existing data if editing

        # Pre-fill values if editing
        self.name_input = TextInput(
            label="Event Name",
            placeholder="Enter event name",
            default=reminder_data['name'] if reminder_data else ""
        )
        self.add_item(self.name_input)

        self.desc_input = TextInput(
            label="Description",
            placeholder="Optional",
            required=False,
            default=reminder_data['description'] if reminder_data else ""
        )
        self.add_item(self.desc_input)

        self.time_input = TextInput(
            label="Time (HH:MM or ISO)",
            placeholder="HH:MM or YYYY-MM-DDTHH:MM",
            required=True,
            default=reminder_data['event_time'].strftime("%Y-%m-%dT%H:%M") if reminder_data else ""
        )
        self.add_item(self.time_input)

        self.pre_reminder_input = TextInput(
            label="Pre-reminder (minutes)",
            placeholder="5",
            default=str(reminder_data['pre_reminder_minutes'] if reminder_data else 5),
            required=False
        )
        self.add_item(self.pre_reminder_input)

        self.location_input = TextInput(
            label="Location",
            placeholder="Optional",
            required=False,
            default=reminder_data['location'] if reminder_data else ""
        )
        self.add_item(self.location_input)

    async def on_submit(self, interaction: Interaction):
        # Validate time
        try:
            time_val = self.time_input.value.strip()
            if len(time_val.split(":")) == 2:  # HH:MM format
                today = datetime.utcnow().date()
                hours, minutes = map(int, time_val.split(":"))
                event_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)
            else:
                event_time = datetime.fromisoformat(time_val)
        except Exception:
            await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)
            return

        # Validate pre_reminder
        try:
            pre_minutes = int(self.pre_reminder_input.value.strip())
        except Exception:
            pre_minutes = 5

        reminder_payload = {
            "guild_id": str(self.guild.id),
            "name": self.name_input.value.strip(),
            "description": self.desc_input.value.strip() or None,
            "channel_id": str(self.channel.id) if self.channel else None,
            "role_id": str(self.role.id) if self.role else None,
            "location": self.location_input.value.strip() or None,
            "interval": self.interval.lower(),
            "event_time": event_time,
            "pre_reminder_minutes": pre_minutes
        }

        try:
            if self.reminder_data:
                # Editing existing reminder
                reminder_id = self.reminder_data['id']
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE reminders SET
                        name=%s, description=%s, channel_id=%s, role_id=%s, location=%s,
                        interval=%s, event_time=%s, pre_reminder_minutes=%s
                    WHERE id=%s
                """, (
                    reminder_payload['name'], reminder_payload['description'], reminder_payload['channel_id'],
                    reminder_payload['role_id'], reminder_payload['location'], reminder_payload['interval'],
                    reminder_payload['event_time'], reminder_payload['pre_reminder_minutes'], reminder_id
                ))
                conn.commit()
                cur.close()
                conn.close()
                await interaction.response.send_message(f"✅ Reminder **{reminder_payload['name']}** updated!", ephemeral=True)
            else:
                # New reminder
                add_reminder_to_db(reminder_payload)
                await interaction.response.send_message(f"✅ Reminder **{reminder_payload['name']}** added!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error saving reminder: {e}", ephemeral=True)

# ------------------------
# Reminder Setup View
# ------------------------
class ReminderSetupView(View):
    def __init__(self, guild, reminder_data=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.reminder_data = reminder_data
        self.channel = None
        self.role = None
        self.interval = "one-time"

        self.add_item(ChannelSelect(guild))
        self.add_item(RoleSelect(guild))
        self.add_item(IntervalSelect())

class ChannelSelect(Select):
    def __init__(self, guild):
        options = [SelectOption(label=c.name, value=str(c.id)) for c in guild.text_channels]
        super().__init__(placeholder="Select Channel", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        self.view.channel = self.view.guild.get_channel(int(self.values[0]))
        await interaction.response.send_modal(ReminderModal(
            self.view.guild, 
            channel=self.view.channel, 
            role=getattr(self.view, "role", None),
            interval=getattr(self.view, "interval", "one-time"),
            reminder_data=getattr(self.view, "reminder_data", None)
        ))

class RoleSelect(Select):
    def __init__(self, guild):
        options = [SelectOption(label=r.name, value=str(r.id)) for r in guild.roles if not r.is_default()]
        options.insert(0, SelectOption(label="No Role", value="none"))
        super().__init__(placeholder="Select Role (Optional)", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        val = self.values[0]
        if val != "none":
            self.view.role = self.view.guild.get_role(int(val))
        else:
            self.view.role = None

class IntervalSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="One-time", value="one-time"),
            SelectOption(label="Daily", value="daily"),
            SelectOption(label="Weekly", value="weekly"),
            SelectOption(label="Monthly", value="monthly")
        ]
        super().__init__(placeholder="Select Interval", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        self.view.interval = self.values[0]

# ------------------------
# Edit / Remove Reminder Dropdowns
# ------------------------
class ReminderSelect(Select):
    def __init__(self, guild, action="edit"):
        self.guild = guild
        self.action = action
        reminders = get_active_reminders()
        reminders = [r for r in reminders if r['guild_id'] == str(guild.id)]
        options = [SelectOption(label=f"{r['name']} ({r['event_time']})", value=str(r['id'])) for r in reminders]
        placeholder = "Select reminder to edit" if action=="edit" else "Select reminder to remove"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        reminder_id = int(self.values[0])
        reminder_data = None
        if self.action == "edit":
            reminders = get_active_reminders()
            reminder_data = next((r for r in reminders if r['id']==reminder_id), None)
            if reminder_data:
                await interaction.response.send_modal(ReminderModal(
                    self.guild,
                    channel=self.guild.get_channel(int(reminder_data['channel_id'])),
                    role=self.guild.get_role(int(reminder_data['role_id'])) if reminder_data['role_id'] else None,
                    interval=reminder_data['interval'],
                    reminder_data=reminder_data
                ))
        else:
            remove_reminder_from_db(reminder_id)
            await interaction.response.send_message("✅ Reminder removed.", ephemeral=True)

class ReminderActionView(View):
    def __init__(self, guild, action="edit"):
        super().__init__(timeout=None)
        self.add_item(ReminderSelect(guild, action=action))

# ------------------------
# Slash Commands
# ------------------------
@bot.tree.command(name="reminder_setup", description="Interactive setup for new reminder")
async def reminder_setup(interaction: Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an admin.", ephemeral=True)
        return
    await interaction.response.send_message("Starting interactive reminder setup...", view=ReminderSetupView(interaction.guild), ephemeral=True)

@bot.tree.command(name="reminder_edit", description="Edit an existing reminder")
async def reminder_edit(interaction: Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    await interaction.response.send_message("Select reminder to edit:", view=ReminderActionView(interaction.guild, action="edit"), ephemeral=True)

@bot.tree.command(name="reminder_remove_ui", description="Remove a reminder via selection")
async def reminder_remove_ui(interaction: Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    await interaction.response.send_message("Select reminder to remove:", view=ReminderActionView(interaction.guild, action="remove"), ephemeral=True)





# ------------------------
# Specializations (aliases + detailed info)
# ------------------------
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
# Load players data into memory
# ------------------------
players_data = load_data()


# ------------------------
# Persistence helpers (per-guild storage)
# ------------------------
def ensure_guild_init(guild_id: int):
    gid = str(guild_id)
    if gid not in players_data:
        players_data[gid] = {spec: [] for spec in SPECIALIZATIONS.keys()}
        save_data(players_data)
    else:
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
    bot.add_view(SpecializationView())
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Slash sync error: {e}")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


async def specialization_autocomplete(interaction: discord.Interaction,
                                      current: str):
    q = (current or "").lower()
    seen = set()
    results = []
    for spec in SPECIALIZATIONS.keys():
        if q in spec.lower():
            results.append(spec)
            seen.add(spec)
    for spec, data in SPECIALIZATIONS.items():
        if spec in seen:
            continue
        if any(q in alias for alias in data["aliases"]):
            results.append(spec)
    return [
        app_commands.Choice(name=spec, value=spec) for spec in results[:25]
    ]


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


@bot.tree.command(name="help", description="Show all available commands.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Villagers & Heroes — Bot Help",
                          color=discord.Color.green())

    # Existing player & specialization commands
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

    # New reminder commands
    embed.add_field(
        name="/reminder_setup",
        value=(
            "Interactive reminder creation.\n"
            "• Select channel for the reminder.\n"
            "• Optionally select a role to ping.\n"
            "• Choose repeat interval: One-time, Daily, Weekly, Monthly.\n"
            "• Enter event name, description, time, pre-reminder minutes, and location.\n"
            "• Pre-reminders are sent automatically before the main reminder."
        ),
        inline=False
    )
    embed.add_field(
        name="/reminder_list",
        value="List all scheduled reminders in this server.",
        inline=False
    )
    embed.add_field(
        name="Time Input",
        value="Time can be entered as `HH:MM` for today or full ISO datetime `YYYY-MM-DDTHH:MM` for one-time events.",
        inline=False
    )
    embed.add_field(
        name="Pre-Reminders",
        value="A separate embed is sent before the main reminder, showing event name, time left, location, description, and tagging role if selected.",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@bot.tree.command(name="specializations",
                  description="Show detailed specialization information.")
async def specializations_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Specializations — Details",
                          color=discord.Color.gold())
    for spec, data in SPECIALIZATIONS.items():
        embed.add_field(name=spec, value=data["info"], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
    save_data(players_data, guild_id=gid, specialization=spec_name, add=added)

    msg = f"✅ Added **{', '.join(added)}** to **{spec_name}**." if added else "ℹ No new names were added."
    await interaction.response.send_message(msg, ephemeral=True)


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
    save_data(players_data, guild_id=gid, specialization=spec_name, remove=removed)

    msg = f"🗑 Removed **{', '.join(removed)}** from **{spec_name}**." if removed else "ℹ None of those names were in the list."
    await interaction.response.send_message(msg, ephemeral=True)


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






# import discord
# from discord.ext import commands
# from discord import app_commands
# from discord.ui import View, Select, Button
# import json
# import os
# from flask import Flask
# from threading import Thread

# # ------------------------
# # Keep-alive (for Replit/uptime pings)
# # ------------------------
# app = Flask('')


# @app.route('/')
# def home():
#     return "Bot is running!"


# def _run():
#     app.run(host='0.0.0.0', port=8080)


# def keep_alive():
#     Thread(target=_run, daemon=True).start()


# # ------------------------
# # Bot configuration
# # ------------------------
# intents = discord.Intents.default()
# intents.message_content = True
# intents.guilds = True
# intents.members = True

# bot = commands.Bot(command_prefix="!", intents=intents)

# DATA_FILE = "players.json"

# # Specializations (aliases + detailed info)
# SPECIALIZATIONS = {
#     "Weapons Masters": {
#         "aliases": ["weapons", "weapon", "wep"],
#         "info": (
#             "- Can skillfully make **Swords, Bows, Axes, Maces, Staffs, and Shields**.\n "
#             "- When crafting these items, the recipe is treated as if it had **one additional star**.\n"
#             "- If the recipe is at **five stars**, the Weapon Master has a chance to produce **Epic gear**.\n "
#             "- Crafted weapons have stats comparable to dropped weapons.\n"
#         )
#     },
#     "Armor Masters": {
#         "aliases": ["armor", "armour"],
#         "info": (
#             "- Can skillfully make **Chest Armor, Gloves, Boots, Belts, and Helms**.\n"
#             "- When crafting any armor, their recipe is treated as if it had **one additional star**.\n "
#             "- If the recipe is at **five stars**, the Armor Master has a chance to produce **Epic gear**.\n"
#         )
#     },
#     "Potions Masters": {
#         "aliases": ["potions", "potion"],
#         "info": (
#             "- Skilled cooks who create Potions and Drams with a chance to gain between **1 and 4 extra potions or drams** per craft without extra ingredients.\n "
#             "- Only they can make **Treasure Drams** (significantly increase Magic Find) and **Malice Drams** (increase both Savagery and Brutality).\n "
#             " **Note:** Bonus potions may be lost if crafting with a full backpack, so free inventory slots are advised.\n"
#         )
#     },
#     "Preparations Masters": {
#         "aliases": ["preparations", "prep"],
#         "info": (
#             "- Skilled at creating preparation items.\n "
#             "- When crafting, the **gold cost is waived** (totally free), but the master must have the gold initially.\n "
#             "- They can make three unique preparations that only they can make: **Wood Pitch** (increases Onslaught on feet), **Mineral Oils** (increase Blasting on helms), and **Leather Stitching** (increases Poise on belts).\n"
#         )
#     },
#     "Production Masters": {
#         "aliases": ["production", "prod"],
#         "info": (
#             "- Skilled with **Motes of Yorick**. Have a bonus **5% Mote Reduction** chance, returning **all motes** when triggered instead of half.\n "
#             "- Earn **50% more crafting experience**."
#         )
#     },
# }



# # ------------------------
# # Persistence helpers (per-guild storage)
# # players_data structure:
# # {
# #   "<guild_id_str>": {
# #       "Weapons Masters": [...],
# #       "Armor Masters": [...],
# #       ...
# #   },
# #   ...
# # }
# # ------------------------
# def load_data():
#     if os.path.exists(DATA_FILE):
#         try:
#             with open(DATA_FILE, "r") as f:
#                 return json.load(f)
#         except Exception:
#             return {}
#     return {}


# def save_data(data):
#     with open(DATA_FILE, "w") as f:
#         json.dump(data, f, indent=4)


# players_data = load_data()


# def ensure_guild_init(guild_id: int):
#     gid = str(guild_id)
#     if gid not in players_data:
#         players_data[gid] = {spec: [] for spec in SPECIALIZATIONS.keys()}
#         save_data(players_data)
#     else:
#         # If code was updated with new specs, ensure keys exist
#         changed = False
#         for spec in SPECIALIZATIONS.keys():
#             if spec not in players_data[gid]:
#                 players_data[gid][spec] = []
#                 changed = True
#         if changed:
#             save_data(players_data)


# def get_spec_name(alias: str):
#     alias = alias.strip().lower()
#     for spec, data in SPECIALIZATIONS.items():
#         if alias == spec.lower() or alias in data["aliases"]:
#             return spec
#     return None


# # ------------------------
# # Persistent Dropdown UI (/menu)
# # ------------------------
# class SpecializationDropdown(Select):

#     def __init__(self):
#         options = [
#             discord.SelectOption(label=spec,
#                                  description=(data["info"].replace("**",
#                                                                    ""))[:80])
#             for spec, data in SPECIALIZATIONS.items()
#         ]
#         super().__init__(
#             placeholder="Select a Specialization",
#             options=options,
#             custom_id="specialization_dropdown"  # required for persistence
#         )

#     async def callback(self, interaction: discord.Interaction):
#         if not interaction.guild:
#             await interaction.response.send_message(
#                 "This can only be used in a server.", ephemeral=True)
#             return
#         ensure_guild_init(interaction.guild.id)
#         gid = str(interaction.guild.id)
#         spec = self.values[0]
#         names = players_data[gid].get(spec, [])
#         # Paginate via a helper view if long
#         await send_paginated_names(interaction, spec, names, ephemeral=True)


# class SpecializationView(View):

#     def __init__(self):
#         super().__init__(timeout=None)  # persistent
#         self.add_item(SpecializationDropdown())


# # ------------------------
# # Pagination View
# # ------------------------
# class PaginationView(View):

#     def __init__(self, embeds, owner: discord.abc.User):
#         super().__init__(timeout=90)
#         self.embeds = embeds
#         self.owner = owner
#         self.idx = 0

#         self.prev_btn = Button(label="⬅ Previous",
#                                style=discord.ButtonStyle.secondary)
#         self.next_btn = Button(label="Next ➡",
#                                style=discord.ButtonStyle.secondary)

#         self.prev_btn.callback = self.prev_page
#         self.next_btn.callback = self.next_page

#         self.add_item(self.prev_btn)
#         self.add_item(self.next_btn)
#         self._update_state()

#     def _update_state(self):
#         self.prev_btn.disabled = (self.idx <= 0)
#         self.next_btn.disabled = (self.idx >= len(self.embeds) - 1)

#     async def prev_page(self, interaction: discord.Interaction):
#         if interaction.user.id != self.owner.id:
#             await interaction.response.send_message(
#                 "You can’t control this pagination.", ephemeral=True)
#             return
#         if self.idx > 0:
#             self.idx -= 1
#             self._update_state()
#         await interaction.response.edit_message(embed=self.embeds[self.idx],
#                                                 view=self)

#     async def next_page(self, interaction: discord.Interaction):
#         if interaction.user.id != self.owner.id:
#             await interaction.response.send_message(
#                 "You can’t control this pagination.", ephemeral=True)
#             return
#         if self.idx < len(self.embeds) - 1:
#             self.idx += 1
#             self._update_state()
#         await interaction.response.edit_message(embed=self.embeds[self.idx],
#                                                 view=self)


# # Helper to send paginated names list
# async def send_paginated_names(interaction: discord.Interaction,
#                                spec_name: str,
#                                names: list[str],
#                                ephemeral: bool = True):
#     if not names:
#         await interaction.response.send_message(
#             f"_No players found for **{spec_name}**._", ephemeral=ephemeral)
#         return

#     chunk_size = 20
#     chunks = [
#         names[i:i + chunk_size] for i in range(0, len(names), chunk_size)
#     ]
#     embeds = []
#     for i, chunk in enumerate(chunks, start=1):
#         embed = discord.Embed(
#             title=f"{spec_name} — Players (Page {i}/{len(chunks)})",
#             description=", ".join(chunk),
#             color=discord.Color.blurple())
#         embeds.append(embed)

#     if len(embeds) == 1:
#         await interaction.response.send_message(embed=embeds[0],
#                                                 ephemeral=ephemeral)
#     else:
#         view = PaginationView(embeds, interaction.user)
#         await interaction.response.send_message(embed=embeds[0],
#                                                 view=view,
#                                                 ephemeral=ephemeral)


# # ------------------------
# # Slash commands
# # ------------------------
# @bot.event
# async def on_ready():
#     # Register persistent view (for messages already using this view)
#     bot.add_view(SpecializationView())
#     # Register slash commands globally
#     try:
#         await bot.tree.sync()
#     except Exception as e:
#         print(f"Slash sync error: {e}")
#     print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


# # Autocomplete for specialization (includes aliases)
# async def specialization_autocomplete(interaction: discord.Interaction,
#                                       current: str):
#     q = (current or "").lower()
#     seen = set()
#     results = []
#     # Canonical names first
#     for spec in SPECIALIZATIONS.keys():
#         if q in spec.lower():
#             results.append(spec)
#             seen.add(spec)
#     # Then alias matches
#     for spec, data in SPECIALIZATIONS.items():
#         if spec in seen:  # already added
#             continue
#         if any(q in alias for alias in data["aliases"]):
#             results.append(spec)
#     return [
#         app_commands.Choice(name=spec, value=spec) for spec in results[:25]
#     ]


# # /menu — show persistent dropdown
# @bot.tree.command(
#     name="menu",
#     description="Show the specialization selection menu (dropdown).")
# async def menu(interaction: discord.Interaction):
#     if not interaction.guild:
#         await interaction.response.send_message(
#             "This can only be used in a server.", ephemeral=True)
#         return
#     ensure_guild_init(interaction.guild.id)
#     await interaction.response.send_message("Choose a specialization:",
#                                             view=SpecializationView(),
#                                             ephemeral=True)


# # /help — rich help
# @bot.tree.command(name="help", description="Show all available commands.")
# async def help_cmd(interaction: discord.Interaction):
#     embed = discord.Embed(title="Villagers & Heroes — Bot Help",
#                           color=discord.Color.green())
#     embed.add_field(name="/menu",
#                     value="Show specialization dropdown menu (browse via UI).",
#                     inline=False)
#     embed.add_field(name="/help",
#                     value="Show this help message.",
#                     inline=False)
#     embed.add_field(name="/specializations",
#                     value="Show detailed specialization info.",
#                     inline=False)
#     embed.add_field(
#         name="/list",
#         value="List players for a specialization (with pagination).",
#         inline=False)
#     embed.add_field(
#         name="/all_players",
#         value="Show all players across all specializations (this server).",
#         inline=False)
#     embed.add_field(name="/add",
#                     value="(Admin only) Add players to a specialization.",
#                     inline=False)
#     embed.add_field(name="/remove",
#                     value="(Admin only) Remove players from a specialization.",
#                     inline=False)
#     await interaction.response.send_message(embed=embed, ephemeral=True)


# # /specializations — detailed descriptions
# @bot.tree.command(name="specializations",
#                   description="Show detailed specialization information.")
# async def specializations_cmd(interaction: discord.Interaction):
#     embed = discord.Embed(title="Specializations — Details",
#                           color=discord.Color.gold())
#     for spec, data in SPECIALIZATIONS.items():
#         embed.add_field(name=spec, value=data["info"], inline=False)
#     await interaction.response.send_message(embed=embed, ephemeral=True)


# # /add — Admin only
# @bot.tree.command(name="add",
#                   description="(Admin only) Add players to a specialization.")
# @app_commands.describe(specialization="Specialization",
#                        names="Comma-separated player names")
# @app_commands.autocomplete(specialization=specialization_autocomplete)
# async def add_cmd(interaction: discord.Interaction, specialization: str,
#                   names: str):
#     if not interaction.guild:
#         await interaction.response.send_message(
#             "This can only be used in a server.", ephemeral=True)
#         return
#     if not interaction.user.guild_permissions.administrator:
#         await interaction.response.send_message(
#             "❌ You must be an Admin to use this command.", ephemeral=True)
#         return

#     ensure_guild_init(interaction.guild.id)
#     gid = str(interaction.guild.id)
#     spec_name = get_spec_name(specialization)
#     if not spec_name:
#         await interaction.response.send_message("❌ Invalid specialization.",
#                                                 ephemeral=True)
#         return

#     names_list = [n.strip() for n in names.split(",") if n.strip()]
#     added = []
#     for n in names_list:
#         if n not in players_data[gid][spec_name]:
#             players_data[gid][spec_name].append(n)
#             added.append(n)
#     save_data(players_data)

#     msg = f"✅ Added **{', '.join(added)}** to **{spec_name}**." if added else "ℹ No new names were added."
#     await interaction.response.send_message(msg, ephemeral=True)


# # /remove — Admin only
# @bot.tree.command(
#     name="remove",
#     description="(Admin only) Remove players from a specialization.")
# @app_commands.describe(specialization="Specialization",
#                        names="Comma-separated player names")
# @app_commands.autocomplete(specialization=specialization_autocomplete)
# async def remove_cmd(interaction: discord.Interaction, specialization: str,
#                      names: str):
#     if not interaction.guild:
#         await interaction.response.send_message(
#             "This can only be used in a server.", ephemeral=True)
#         return
#     if not interaction.user.guild_permissions.administrator:
#         await interaction.response.send_message(
#             "❌ You must be an Admin to use this command.", ephemeral=True)
#         return

#     ensure_guild_init(interaction.guild.id)
#     gid = str(interaction.guild.id)
#     spec_name = get_spec_name(specialization)
#     if not spec_name:
#         await interaction.response.send_message("❌ Invalid specialization.",
#                                                 ephemeral=True)
#         return

#     names_list = [n.strip() for n in names.split(",") if n.strip()]
#     removed = []
#     for n in names_list:
#         if n in players_data[gid][spec_name]:
#             players_data[gid][spec_name].remove(n)
#             removed.append(n)
#     save_data(players_data)

#     msg = f"🗑 Removed **{', '.join(removed)}** from **{spec_name}**." if removed else "ℹ None of those names were in the list."
#     await interaction.response.send_message(msg, ephemeral=True)


# # /list — with pagination
# @bot.tree.command(
#     name="list",
#     description="List players for a specialization (this server).")
# @app_commands.describe(specialization="Specialization")
# @app_commands.autocomplete(specialization=specialization_autocomplete)
# async def list_cmd(interaction: discord.Interaction, specialization: str):
#     if not interaction.guild:
#         await interaction.response.send_message(
#             "This can only be used in a server.", ephemeral=True)
#         return

#     ensure_guild_init(interaction.guild.id)
#     gid = str(interaction.guild.id)
#     spec_name = get_spec_name(specialization)
#     if not spec_name:
#         await interaction.response.send_message("❌ Invalid specialization.",
#                                                 ephemeral=True)
#         return

#     names = players_data[gid].get(spec_name, [])
#     await send_paginated_names(interaction, spec_name, names, ephemeral=True)


# # /all_players — per server only
# @bot.tree.command(
#     name="all_players",
#     description=
#     "Show all players across all specializations (this server only).")
# async def all_players_cmd(interaction: discord.Interaction):
#     if not interaction.guild:
#         await interaction.response.send_message(
#             "This can only be used in a server.", ephemeral=True)
#         return

#     ensure_guild_init(interaction.guild.id)
#     gid = str(interaction.guild.id)

#     embed = discord.Embed(title="All Players — This Server",
#                           color=discord.Color.green())
#     empty = True
#     for spec in SPECIALIZATIONS.keys():
#         names = players_data[gid].get(spec, [])
#         if names:
#             empty = False
#         embed.add_field(name=spec,
#                         value=", ".join(names) if names else "_None_",
#                         inline=False)

#     if empty:
#         await interaction.response.send_message(
#             "_No players found in this server yet._", ephemeral=True)
#     else:
#         await interaction.response.send_message(embed=embed, ephemeral=True)


# # ------------------------
# # Run
# # ------------------------
# keep_alive()
# TOKEN = os.getenv("DISCORD_TOKEN")
# if not TOKEN:
#     raise ValueError("DISCORD_TOKEN is not set.")
# bot.run(TOKEN)




