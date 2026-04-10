# Claude (tmux) Telegram Bridge

Remote control your Claude Code CLI session from your phone via Telegram.
Get push notifications when Claude needs your input, reply by voice dictation.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram, message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow the prompts, pick a name
3. Copy the bot token

### 2. Get Your Chat ID

1. Message your new bot (send any message like "hello")
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
3. Find `"chat":{"id":XXXXXXXX}` in the JSON — that's your chat ID

### 3. Configure

```bash
cd ~/Projects/claude-telegram-bridge
cp .env.example .env
# Edit .env with your BOT_TOKEN and CHAT_ID
```

### 4. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Start Everything

```bash
~/Projects/claude-telegram-bridge/launcher.sh
```

This creates a tmux session with Claude Code + the bridge. You'll get a Telegram message confirming the bridge is connected.

### From Your Phone

- **Receive notifications** when Claude needs your input
- **Reply** with text or voice dictation to respond
- `/screen` — see current terminal output
- `/status` — check if Claude is working or waiting
- `/stop` — shut down the bridge

### Come Back to Your Laptop

```bash
tmux attach -t claude
```

### Stop the Bridge Only

Send `/stop` in Telegram, or switch to the bridge window in tmux and press Ctrl+C.
