# Goldfish - Rosebud-Style Journaling Assistant

A minimal, gentle journaling chatbot that provides supportive conversation and guided reflection.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

   Or copy `.env.example` to `.env` and add your key there.

3. **Run the app:**

   **Web Interface (Recommended):**
   ```bash
   python run_web.py
   ```
   Then open your browser to: http://localhost:5000

   **Command Line Interface:**
   ```bash
   python main.py
   ```

## Features

- 🌸 Gentle, supportive conversation style
- 💾 Automatic session saving
- 📱 Beautiful web interface with gradient design
- 💬 Real-time chat with typing indicators
- 📝 Conversation history tracking
- 🎯 CLI interface with simple commands

## Web Interface Features

- Calming gradient background
- Real-time chat interface
- Typing indicators
- New session and save session buttons
- Mobile-responsive design
- Auto-focus input field

## CLI Commands

- `quit` or `exit` - End session
- `save` - Save current session
- Ctrl+C - Emergency exit with auto-save

## Session Files

Sessions are automatically saved to the `sessions/` directory with timestamps.