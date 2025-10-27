#!/usr/bin/env python3
"""
Goldfish Web App Launcher
Simple script to start the web application
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def check_requirements():
    """Check if required dependencies are installed"""
    try:
        import flask
        import openai
        print("✓ Dependencies found")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("\nPlease install requirements:")
        print("pip install -r requirements.txt")
        return False

def check_api_key():
    """Check if OpenAI API key is configured"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OpenAI API key not found")
        print("\nPlease set your API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        print("\nOr create a .env file with:")
        print("OPENAI_API_KEY=your-api-key-here")
        return False

    print("✓ OpenAI API key configured")
    return True

def main():
    """Main launcher function"""
    print("🌸 Goldfish Journaling Assistant - Web Version")
    print("=" * 50)

    # Check dependencies
    if not check_requirements():
        sys.exit(1)

    # Check API key
    if not check_api_key():
        print("\n⚠️  Warning: The app will start but chat won't work without an API key")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)

    print("\n🚀 Starting web application...")
    print("📱 Open your browser to: http://localhost:3000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50 + "\n")

    # Import and run the Flask app
    try:
        from app import app
        app.run(debug=False, host='0.0.0.0', port=3000)
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye! Thanks for journaling with Goldfish.")
    except Exception as e:
        print(f"\n❌ Error starting app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()