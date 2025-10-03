# Villagers & Heroes Discord Bot

This is a Discord bot designed for managing players and their specializations in the game "Villagers & Heroes." The bot features interactive UI elements, slash commands, per-server player data persistence, and a Flask-based keep-alive mechanism suitable for hosting on platforms like Render or Replit.

---

## Features

* **Specialization Management:** Track players under different specializations such as Weapons Masters, Armor Masters, Potions Masters, Preparations Masters, and Production Masters.
* **Persistent Dropdown Menu:** Users can select a specialization from a persistent dropdown and view players in that category.
* **Pagination:** Player lists with many entries are paginated for easier viewing.
* **Admin Commands:** Add or remove players from specializations using `/add` and `/remove` commands.
* **Rich Help & Info:** Use `/help` to view commands and `/specializations` to get detailed specialization descriptions.
* **Server-Specific Data:** Each Discord server has its own data storage for players.
* **Keep-Alive Support:** Flask server for uptime pings ensures the bot stays running when hosted on platforms like Render.

---

## Commands

| Command                            | Description                                                                      |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| `/menu`                            | Show the specialization selection menu (dropdown).                               |
| `/help`                            | Display help message with all available commands.                                |
| `/specializations`                 | Show detailed specialization information.                                        |
| `/list <specialization>`           | List all players in a specialization (paginated).                                |
| `/all_players`                     | Show all players across all specializations for this server.                     |
| `/add <specialization> <names>`    | **Admin only:** Add players to a specialization. Names are comma-separated.      |
| `/remove <specialization> <names>` | **Admin only:** Remove players from a specialization. Names are comma-separated. |

---

## Installation & Setup

1. **Clone the repository:**

```bash
git clone <repository-url>
cd <repository-folder>
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**

Create a `.env` file (or set environment variables on Render) with your Discord bot token:

```
DISCORD_TOKEN=your_discord_bot_token_here
```

4. **Run the bot locally:**

```bash
python bot.py
```

5. **Hosting on Render:**

   * Ensure your Render service exposes port `8080` for keep-alive pings.
   * Render will automatically keep the Flask server alive, allowing Discord interactions to continue.

---

## Data Storage

* Players data is stored in a JSON file called `players.json`.
* Data is structured per server (guild), ensuring separate player lists per Discord server.
* The bot automatically initializes data for new servers and updates data when new specializations are added.

Example structure:

```json
{
  "<guild_id>": {
    "Weapons Masters": ["Player1", "Player2"],
    "Armor Masters": [],
    "Potions Masters": [],
    "Preparations Masters": [],
    "Production Masters": []
  }
}
```

---

## Specializations

* **Weapons Masters:** Craft weapons with enhanced quality and chance for Epic gear.
* **Armor Masters:** Craft armor with improved quality and chance for Epic gear.
* **Potions Masters:** Create potions with bonus quantity and unique effects.
* **Preparations Masters:** Produce preparations for free and craft unique items.
* **Production Masters:** Handle Motes of Yorick with experience and resource benefits.

---

## Contributing

Contributions are welcome! Please fork the repository, make your changes, and open a pull request.

---

## License

This project is licensed under the MIT License.
