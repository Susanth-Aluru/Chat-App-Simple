# ChatFlow 💬

A classy WhatsApp-style group chat app built with Python + Flask.
No database — just text files. Perfect for demos!

## Setup & Run

```bash
pip install flask
python app.py
```

Then open: http://localhost:5000

## How it works

- **Users** stored in `data/users.txt` (username:hashed_password)
- **Messages** stored in `data/messages.txt` (timestamp|sender|color|text)
- Auto-polls every 1.5 seconds for new messages — real-time feel!
- Each user gets a unique color avatar

## Features

- ✅ Register & Login
- ✅ Real-time group chat (polling)
- ✅ Color-coded user avatars
- ✅ Message bubbles (own = right, others = left)
- ✅ Timestamps & day dividers
- ✅ Enter to send, Shift+Enter for newline
- ✅ Dark, classy UI inspired by susanth.netlify.app
