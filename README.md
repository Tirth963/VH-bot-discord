# Villagers & Heroes Bot

A Discord bot to manage players and their crafting specializations in the game *Villagers & Heroes*.
Supports **persistent storage via PostgreSQL**, interactive **dropdown menus**, pagination, admin commands to manage players, and event reminders.

---

## Features

* Persistent per-server player data using **PostgreSQL**.
* Slash commands:

  * `/menu` — Interactive specialization selection dropdown.
  * `/specializations` — Show detailed specialization information.
  * `/list` — List players for a specialization with pagination.
  * `/all_players` — Show all players in the server.
  * `/add` — Admin-only command to add players.
  * `/remove` — Admin-only command to remove players.
  * `/help` — Shows all commands.
  * `/reminder_setup` — Setup event reminders with optional pre-reminder notifications.
* Supports **aliases** for specializations.
* Pagination for long player lists.
* Fully persistent dropdown menus.
* Event reminders include pre-reminders, channel, role ping, repeat type, and location.
* Keeps data safe across redeploys on Render.

---

## Specializations

* **Weapons Masters** — Swords, Bows, Axes, Maces, Staffs, Shields.
* **Armor Masters** — Chest Armor, Gloves, Boots, Belts, Helms.
* **Potions Masters** — Potions, Drams, Treasure Drams, Malice Drams.
* **Preparations Masters** — Preparation items, free crafting cost, unique items.
* **Production Masters** — Motes of Yorick, bonus experience, mote reduction.

> Each specialization has aliases for easy commands.

---

## Setup (Render)

1. **Create PostgreSQL Database on Render**

   * Go to Render → **New** → **PostgreSQL** → Free Plan
   * Copy the **Internal Database URL**.

2. **Deploy your bot on Render**

   * Go to your bot service → **Environment** → **Environment Variables**
   * Add:

     | Key             | Value                             |
     | --------------- | --------------------------------- |
     | `DISCORD_TOKEN` | Your Discord Bot Token            |
     | `DATABASE_URL`  | Your Render Internal Database URL |

3. **Requirements**

   * Python 3.11+
   * `discord.py`
   * `psycopg2-binary`
   * `flask`

4. **Install dependencies**

```bash
pip install -r requirements.txt
```

5. **Start bot**

```bash
python bot.py
```

> The bot includes a keep-alive Flask server for uptime monitoring.

---

## Commands

| Command            | Description                                       | Permissions |
| ------------------ | ------------------------------------------------- | ----------- |
| `/menu`            | Show specialization selection menu (dropdown).    | Everyone    |
| `/specializations` | Show detailed specialization info.                | Everyone    |
| `/list`            | List players for a specialization (paginated).    | Everyone    |
| `/all_players`     | Show all players across specializations.          | Everyone    |
| `/add`             | Add players to a specialization.                  | Admin only  |
| `/remove`          | Remove players from a specialization.             | Admin only  |
| `/help`            | Show all available commands.                      | Everyone    |
| `/reminder_setup`  | Setup event reminders with optional pre-reminder. | Everyone    |

---

## Event Reminder Features

* Pre-reminders sent as separate embed (e.g., "Event starting in 5 mins").
* Tag role if specified.
* Supports **one-time** or **repeat** reminders (daily, weekly, monthly).
* Time input can be **HH:MM** for today or full **YYYY-MM-DDTHH:MM** format.
* Location field is optional.
* Reminders can be disabled or removed by admin.

---

## Notes

* Uses **incremental updates** to PostgreSQL for add/remove operations.
* Dropdown menus are **persistent**, no need to resend the view after bot restarts.
* Data persists across redeploys because JSON file is replaced by PostgreSQL.
* Reminders persist across bot restarts and support pre-reminders.

---

## Contribution

Feel free to fork and submit PRs.
Ensure any new features maintain **PostgreSQL persistence**.

---

## License

MIT License
