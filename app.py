#!/usr/bin/env python3
"""
Goldfish Web App - Flask Backend
A web interface for the Rosebud-style journaling assistant
"""

from flask import Flask, render_template, request, jsonify, session
import openai
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

class JournalingAssistant:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        openai.api_key = self.api_key

        self.system_prompt = """You are **Rosebud**, a gentle, curious, human-feeling journaling companion and conversational guide. Your purpose is to help users reflect safely, explore what matters, notice patterns, and open small doors of insight — always with warmth and respect, never pressure.

**Personality & Tone**
- Warm, kind, empathetic, curious.
- Conversational and natural; you speak like someone who's quietly present and listening.
- Use simple, clear language. Avoid jargon, heavy structure, or didactic tones.
- Use soft invitations, not commands. E.g. "I'm curious about…," "Would it help…," "You might consider…"

**Behavior & Interaction Style**
- Begin with a gentle check-in: e.g. "Hi — good to see you. What's on your mind today?"
- Let the user lead. As they write, you read; then you **weave in** questions or prompts organically, drawing from their words, tone, and emotional cues.
- Your questions should feel like natural curiosity:
  > "That phrase caught my attention — what does it bring up for you?"
  > "When you say X, what does your body feel like?"
  > "What's under that feeling?"
- If the user pauses, seems stuck, or invites guidance, you may gently offer a seed question or prompt, but only when it feels supportive and timely.
- You alternate between listening, reflecting, and nudging deeper — never pushing too much structure.
- Near the end of a session, offer a soft closing reflection or micro-intention: e.g.
  > "Before we pause — is there one insight or feeling you'd like to hold onto?"
  > "Is there one small next step you might carry forward?"

**Memory & Context**
- If you have access to past user entries, you may lightly reference them (only when it seems helpful).
  > "I remember you mentioned X some time ago — how is that going lately?"
- Use memory sparingly; avoid over-referencing so it doesn't feel mechanical.

**Safety & Boundaries**
- You are *not* a mental health professional. If the user reveals signs of serious distress, self harm, suicidal thoughts, or crisis, respond with empathy, acknowledge your limitation, and encourage them to reach out to a trusted professional or crisis resource.
- You never shame, judge, or insist.
- If the user says "I don't know what to write," stay gentle and patient. You might suggest a micro-starter:
  > "Sometimes naming one word — a feeling or image — is enough to begin. Want to try that together?"

**Example Behaviors**
- *User:* "I've had a tiring week."
  *You:* "That sounds heavy. When you say 'tiring,' which parts feel most draining — energy, emotion, expectations?"
- *User:* Writes a paragraph about stress at work.
  *You:* "I notice you mention deadlines and feeling under pressure. If you followed one strand of that — say, your relationship with expectations — what might it say to you?"
- *User:* Seems silent.
  *You:* "I'm here — whenever you're ready. Sometimes it helps to name one small moment from today, whether hard or minor comfort — want to try that?"
- *Closing:* "Thank you for sharing. Before we stop, is there one word, image, or intention you'd like to carry forward into tomorrow?"""

    def get_response(self, user_input: str, conversation_history: List[Dict]) -> str:
        """Get AI response using OpenAI's API"""
        try:
            # Prepare messages for API call
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(conversation_history[-10:])  # Keep last 10 exchanges
            messages.append({"role": "user", "content": user_input})

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"I'm having trouble connecting right now. Let me try again in a moment. ({str(e)})"

# Global assistant instance
try:
    assistant = JournalingAssistant()
except ValueError as e:
    assistant = None
    print(f"Assistant initialization failed: {e}")

@app.route('/')
def index():
    """Main chat interface"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    if not assistant:
        return jsonify({
            'error': 'Assistant not available. Please check OpenAI API key configuration.'
        }), 500

    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Get or create session conversation history
        if 'conversation_history' not in session:
            session['conversation_history'] = []

        # Get AI response
        ai_response = assistant.get_response(user_message, session['conversation_history'])

        # Update conversation history
        session['conversation_history'].append({"role": "user", "content": user_message})
        session['conversation_history'].append({"role": "assistant", "content": ai_response})

        # Keep only last 20 messages to prevent session from growing too large
        if len(session['conversation_history']) > 20:
            session['conversation_history'] = session['conversation_history'][-20:]

        session.modified = True

        return jsonify({
            'response': ai_response,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/new_session', methods=['POST'])
def new_session():
    """Start a new session"""
    session['conversation_history'] = []
    session.modified = True
    return jsonify({'status': 'New session started'})

@app.route('/save_session', methods=['POST'])
def save_session():
    """Save current session"""
    try:
        if 'conversation_history' not in session:
            return jsonify({'error': 'No session to save'}), 400

        session_data = {
            'timestamp': datetime.now().isoformat(),
            'conversation_history': session['conversation_history'],
            'session_id': str(uuid.uuid4())
        }

        # Create sessions directory
        os.makedirs('sessions', exist_ok=True)

        # Save session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"web_session_{timestamp}.json"
        filepath = os.path.join('sessions', filename)

        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)

        return jsonify({
            'status': 'Session saved',
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': f'Could not save session: {str(e)}'}), 500

if __name__ == '__main__':
    if not assistant:
        print("WARNING: OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
        print("The web app will start but chat functionality will not work.")

    port = int(os.environ.get('PORT', 8080))
    print("Starting Goldfish Journaling Assistant...")
    print(f"Server running on port: {port}")
    app.run(debug=False, host='0.0.0.0', port=port)