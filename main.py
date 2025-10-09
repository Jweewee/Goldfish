#!/usr/bin/env python3
"""
Goldfish - A Rosebud-style Journaling Assistant
Minimal implementation of a gentle, guided journaling chatbot
"""

import openai
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class JournalingAssistant:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        openai.api_key = self.api_key
        self.conversation_history = []
        self.session_data = {}

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
- *Closing:* "Thank you for sharing. Before we stop, is there one word, image, or intention you'd like to carry forward into tomorrow?""""

    def get_response(self, user_input: str) -> str:
        """Get AI response using OpenAI's API"""
        try:
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})

            # Prepare messages for API call
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history[-10:])  # Keep last 10 exchanges

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )

            assistant_response = response.choices[0].message.content.strip()

            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            return assistant_response

        except Exception as e:
            return f"I'm having trouble connecting right now. Let me try again in a moment. ({str(e)})"

    def save_session(self, filename: Optional[str] = None):
        """Save current session to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"journal_session_{timestamp}.json"

        session_data = {
            "timestamp": datetime.now().isoformat(),
            "conversation_history": self.conversation_history,
            "session_data": self.session_data
        }

        os.makedirs("sessions", exist_ok=True)
        filepath = os.path.join("sessions", filename)

        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)

        return filepath

    def load_session(self, filepath: str):
        """Load previous session from file"""
        try:
            with open(filepath, 'r') as f:
                session_data = json.load(f)

            self.conversation_history = session_data.get("conversation_history", [])
            self.session_data = session_data.get("session_data", {})

            return True
        except Exception as e:
            print(f"Error loading session: {e}")
            return False

class ChatInterface:
    def __init__(self):
        self.assistant = None

    def setup_assistant(self):
        """Initialize the journaling assistant"""
        try:
            self.assistant = JournalingAssistant()
            return True
        except ValueError as e:
            print(f"Setup error: {e}")
            print("Please set your OpenAI API key as an environment variable:")
            print("export OPENAI_API_KEY='your-api-key-here'")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    def start_session(self):
        """Start a new journaling session"""
        print("\n" + "="*50)
        print("🌸 Welcome to Goldfish Journaling Assistant 🌸")
        print("="*50)
        print("A gentle space for reflection and growth")
        print("Type 'quit' to end session, 'save' to save current session")
        print("="*50 + "\n")

        # Initial greeting
        initial_response = self.assistant.get_response("Hello")
        print(f"Goldfish: {initial_response}\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    self.end_session()
                    break
                elif user_input.lower() == 'save':
                    filepath = self.assistant.save_session()
                    print(f"Session saved to: {filepath}")
                    continue
                elif not user_input:
                    continue

                response = self.assistant.get_response(user_input)
                print(f"\nGoldfish: {response}\n")

            except KeyboardInterrupt:
                print("\n\nSession interrupted. Saving your conversation...")
                self.end_session()
                break
            except Exception as e:
                print(f"Error: {e}")
                continue

    def end_session(self):
        """End the current session"""
        print("\nThank you for taking time to reflect today.")
        print("Your thoughts and feelings matter. Take care of yourself. 🌱")

        # Auto-save session
        try:
            filepath = self.assistant.save_session()
            print(f"Session automatically saved to: {filepath}")
        except Exception as e:
            print(f"Could not save session: {e}")

def main():
    """Main application entry point"""
    interface = ChatInterface()

    if not interface.setup_assistant():
        return

    interface.start_session()

if __name__ == "__main__":
    main()