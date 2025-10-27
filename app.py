#!/usr/bin/env python3
"""
Goldfish Web App - Flask Backend
A web interface for the Rosebud-style journaling assistant with Supabase integration
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import openai
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import uuid
from dotenv import load_dotenv
from functools import wraps
import logging

# Load environment variables from .env file
load_dotenv()

# Import services
from services.auth_service import auth_service
from services.journal_service import journal_service
from services.embedding_service import embedding_service
from services.rag_service import rag_service
from services.summary_service import summary_service

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication decorator
def require_auth(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = auth_service.get_current_user()
        if not user:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

    def get_response(self, user_input: str, conversation_history: List[Dict], user_id: str = None) -> str:
        """Get AI response using OpenAI's API with RAG context"""
        try:
            # Get relevant context from past entries if user is authenticated
            context = ""
            if user_id:
                try:
                    context_result = rag_service.get_relevant_context(user_id, user_input)
                    if context_result["success"] and context_result["context"]:
                        context = context_result["context"]
                except Exception as e:
                    logger.warning(f"RAG context retrieval failed: {str(e)}")
            logger.info(f"RAG context for user_id {user_id}: [{context}]")
            
            # Enhance system prompt with context
            enhanced_prompt = rag_service.enhance_system_prompt(self.system_prompt, context)
            
            # Prepare messages for API call
            messages = [{"role": "system", "content": enhanced_prompt}]
            messages.extend(conversation_history[-10:])  # Keep last 10 exchanges
            messages.append({"role": "user", "content": user_input})

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Get response error: {str(e)}")
            return f"I'm having trouble connecting right now. Let me try again in a moment. ({str(e)})"

# Global assistant instance
try:
    assistant = JournalingAssistant()
except ValueError as e:
    assistant = None
    print(f"Assistant initialization failed: {e}")

# Authentication Routes
@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """User registration API"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_service.sign_up(email, password)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'user': {
                    'id': result['user'].id,
                    'email': result['user'].email
                }
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login API"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_service.sign_in(email, password)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'user': {
                    'id': result['user'].id,
                    'email': result['user'].email
                }
            })
        else:
            return jsonify({'error': result['error']}), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """User logout API"""
    try:
        result = auth_service.sign_out()
        return jsonify({'success': True, 'message': result['message']})
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/api/auth/user', methods=['GET'])
def api_get_user():
    """Get current user API"""
    try:
        user = auth_service.get_current_user()
        if user:
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'user': None})
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500

# Page Routes
@app.route('/')
def index():
    """Landing page - redirect to login"""
    user = auth_service.get_current_user()
    if user:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/auth/callback')
def auth_callback():
    """Handle Supabase auth callback"""
    try:
        # Get the access token from URL fragment
        access_token = request.args.get('access_token')
        refresh_token = request.args.get('refresh_token')
        
        if access_token and refresh_token:
            # Set the session with the tokens
            if auth_service.set_session(access_token, refresh_token):
                # Get user info
                user = auth_service.get_current_user()
                if user:
                    return redirect(url_for('home'))
        
        # If no tokens or user not found, redirect to login
        return redirect(url_for('login'))
        
    except Exception as e:
        logger.error(f"Auth callback error: {str(e)}")
        return redirect(url_for('login'))

@app.route('/login')
def login():
    """Login/signup page"""
    return render_template('login.html')

@app.route('/home')
@require_auth
def home():
    """Dashboard after login"""
    user = auth_service.get_current_user()
    recent_entries = journal_service.get_recent_entries(user['id'], limit=5)
    return render_template('home.html', user=user, recent_entries=recent_entries.get('entries', []))

@app.route('/entries')
@require_auth
def entries():
    """View all journal entries"""
    user = auth_service.get_current_user()
    all_entries = journal_service.get_user_entries(user['id'])
    return render_template('entries.html', user=user, entries=all_entries.get('entries', []))

@app.route('/new-entry')
@require_auth
def new_entry():
    """Start new journal session"""
    user = auth_service.get_current_user()
    return render_template('new-entry.html', user=user)

# API Routes
@app.route('/chat', methods=['POST'])
@require_auth
def chat():
    """Handle chat messages with RAG"""
    if not assistant:
        return jsonify({
            'error': 'Assistant not available. Please check OpenAI API key configuration.'
        }), 500

    try:
        user = auth_service.get_current_user()
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Get or create session conversation history
        if 'conversation_history' not in session:
            session['conversation_history'] = []

        # Get AI response with RAG context
        ai_response = assistant.get_response(user_message, session['conversation_history'], user['id'])

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
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/new_session', methods=['POST'])
@require_auth
def new_session():
    """Start a new session"""
    session['conversation_history'] = []
    session.modified = True
    return jsonify({'status': 'New session started'})

@app.route('/save_entry', methods=['POST'])
@require_auth
def save_entry():
    """Save journal entry to Supabase with embeddings"""
    try:
        user = auth_service.get_current_user()
        
        if 'conversation_history' not in session or not session['conversation_history']:
            return jsonify({'error': 'No conversation to save'}), 400

        # Generate summary
        summary = summary_service.generate_summary(session['conversation_history'])
        
        # Save entry to database
        result = journal_service.save_entry(
            user_id=user['id'],
            conversation_history=session['conversation_history'],
            summary=summary
        )
        
        if not result['success']:
            return jsonify({'error': result['error']}), 500
        
        entry_id = result['entry']['id']
        
        # Generate and store embeddings
        chunks = embedding_service.chunk_conversation(session['conversation_history'])
        embedding_result = embedding_service.store_embeddings(entry_id, user['id'], chunks)
        
        if not embedding_result['success']:
            logger.warning(f"Failed to store embeddings: {embedding_result['error']}")
        
        # Clear session
        session['conversation_history'] = []
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': 'Entry saved successfully',
            'entry_id': entry_id
        })

    except Exception as e:
        logger.error(f"Save entry error: {str(e)}")
        return jsonify({'error': f'Could not save entry: {str(e)}'}), 500

@app.route('/api/entries', methods=['GET'])
@require_auth
def api_get_entries():
    """Get user's journal entries"""
    try:
        user = auth_service.get_current_user()
        result = journal_service.get_user_entries(user['id'])
        
        if result['success']:
            return jsonify({
                'success': True,
                'entries': result['entries'],
                'count': result['count']
            })
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        logger.error(f"Get entries error: {str(e)}")
        return jsonify({'error': 'Failed to get entries'}), 500

@app.route('/api/entries/<entry_id>', methods=['GET'])
@require_auth
def api_get_entry(entry_id):
    """Get specific journal entry"""
    try:
        user = auth_service.get_current_user()
        result = journal_service.get_entry_by_id(entry_id)
        
        if result['success']:
            # Check if user owns this entry
            if result['entry']['user_id'] != user['id']:
                return jsonify({'error': 'Unauthorized'}), 403
            
            return jsonify({
                'success': True,
                'entry': result['entry']
            })
        else:
            return jsonify({'error': result['error']}), 404
            
    except Exception as e:
        logger.error(f"Get entry error: {str(e)}")
        return jsonify({'error': 'Failed to get entry'}), 500

@app.route('/api/entries/<entry_id>', methods=['DELETE'])
@require_auth
def api_delete_entry(entry_id):
    """Delete journal entry"""
    try:
        user = auth_service.get_current_user()
        result = journal_service.delete_entry(entry_id, user['id'])
        
        if result['success']:
            return jsonify({'success': True, 'message': result['message']})
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        logger.error(f"Delete entry error: {str(e)}")
        return jsonify({'error': 'Failed to delete entry'}), 500

if __name__ == '__main__':
    if not assistant:
        print("WARNING: OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
        print("The web app will start but chat functionality will not work.")

    port = int(os.environ.get('PORT', 8080))
    print("Starting Goldfish Journaling Assistant...")
    print(f"Server running on port: {port}")
    app.run(debug=False, host='0.0.0.0', port=port)