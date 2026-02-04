# Discord Puzzle Trading Bot

A production-ready Discord bot that helps players coordinate puzzle piece trading for a mobile game. The bot tracks inventory through image scanning and provides coordination commands, but does **NOT** execute trades or enforce game state.

## Features

- 📸 **Image Scanning**: Upload screenshots to automatically detect puzzle pieces
- 📦 **Inventory Tracking**: Keep track of your pieces and duplicates
- 🔍 **Trade Coordination**: Find who has pieces you need
- ✅ **Trade Recording**: Report completed in-game trades
- 🔒 **Safety First**: Stars are immutable, duplicates only decrease via explicit commands

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- Tesseract OCR installed ([Installation guide](https://github.com/tesseract-ocr/tesseract))

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wos-puzzles-trades
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_TOKEN
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Learn how to use the bot |
| `/scan` | Upload puzzle screenshots to update inventory |
| `/inventory [scene]` | View your inventory (optionally filtered by scene) |
| `/need <scene>` | Find pieces you're missing in a scene |
| `/whohas <scene> <slot>` | Find who has a specific piece |
| `/used <scene> <slot>` | Report that you traded a piece in-game |
| `/fix` | Manually correct your inventory |

## How It Works

1. **Upload Screenshots**: Use `/scan` and upload images of your puzzle inventory
2. **Automatic Detection**: The bot uses computer vision to detect pieces, stars, and duplicates
3. **Smart Merging**: New pieces are added, duplicates can increase, but never decrease automatically
4. **Conflict Resolution**: If scanned values are lower than stored, the bot asks for confirmation
5. **Trade Coordination**: Use `/need` and `/whohas` to find trading partners
6. **Manual Updates**: Use `/used` after completing trades to keep inventory accurate

## Core Rules

⭐ **Stars are immutable** - Once detected, star counts never change  
🔁 **Duplicates only increase automatically** - Decreases require explicit `/used` command  
❌ **Images can't reduce duplicates** - Prevents accidental data loss  
✅ **User commands override everything** - You have full control via `/fix`  
📊 **Database is source of truth** - Not the images  

## Architecture

```
wos-puzzles-trades/
├── bot.py                 # Entry point
├── config.py              # Configuration
├── requirements.txt       # Dependencies
│
├── db/                    # Database layer
│   ├── database.py        # Connection manager
│   └── schema.sql         # SQLite schema
│
├── inventory/             # Inventory logic
│   ├── merge.py           # Merge logic (CRITICAL)
│   ├── queries.py         # Database queries
│   └── rules.py           # Validation rules
│
├── vision/                # Image processing
│   ├── pipeline.py        # Main orchestrator
│   ├── grid_detector.py   # Tile detection
│   ├── tile_parser.py     # Star/duplicate detection
│   └── ocr.py             # Text extraction
│
├── bot/                   # Discord bot
│   ├── client.py          # Bot client
│   ├── events.py          # Event handlers
│   └── commands/          # Command implementations
│       ├── start.py
│       ├── scan.py
│       ├── inventory.py
│       ├── need.py
│       ├── whohas.py
│       ├── used.py
│       └── fix.py
│
└── utils/                 # Utilities
    ├── image_hash.py      # Deduplication
    └── validation.py      # Input validation
```

## Deployment

### Railway (Recommended)

1. **Connect your GitHub repository** to [Railway.app](https://railway.app/).
2. **Add Environment Variables**:
   - `DISCORD_TOKEN`: `your_token_here`
   - `DATABASE_URL`: `/app/data/puzzle_bot.db`
3. **Mount a Volume**:
   - In Railway Settings, add a **Volume**.
   - Mount path: `/app/data` (This makes your SQLite database permanent).
4. **Deploy**: Railway will automatically detect the `Dockerfile` and deploy.

### Fly.io (Alternative)
*Requires a credit card on file even for free tier.*

### Environment Variables

Required:
- `DISCORD_TOKEN` - Your Discord bot token

Optional:
- `DATABASE_URL` - Database path (default: `puzzle_bot.db`)
- `TESSERACT_PATH` - Path to Tesseract executable
- `LOG_LEVEL` - Logging level (default: `INFO`)

## Vision Pipeline Notes

The vision pipeline uses:
- **OpenCV** for grid detection and image processing
- **Tesseract OCR** for scene title extraction
- **Color detection** for star and duplicate badge detection
- **Perceptual hashing** for duplicate image detection

**Important**: Vision accuracy depends on consistent UI layout in the mobile game. If the game UI changes significantly, the detection logic may need adjustment.

## Database

Uses SQLite by default for easy deployment. Schema includes:
- `users` - Discord user mapping
- `inventory` - Piece ownership
- `scan_history` - Audit trail
- `image_hashes` - Deduplication

Easy migration path to PostgreSQL by changing `DATABASE_URL`.

## Contributing

Contributions welcome! Please ensure:
- Code follows existing patterns
- Critical rules (immutable stars, safe merging) are preserved
- Tests pass (when implemented)

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check existing GitHub issues
2. Create a new issue with details
3. Join our Discord server (link)

---

**Remember**: This bot is informational only. Real trades happen inside the mobile game!
