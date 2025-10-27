"""
Summary service for generating conversation summaries using GPT
"""
from typing import List, Dict, Any
import openai
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class SummaryService:
    """Service for generating conversation summaries"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
        # Initialize OpenAI client
        openai.api_key = self.api_key
    
    def generate_summary(self, conversation_history: List[Dict]) -> str:
        """
        Generate a summary of the conversation
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            Summary string
        """
        try:
            # Format conversation for summarization
            conversation_text = self._format_conversation_for_summary(conversation_history)
            
            # Create summary prompt
            summary_prompt = f"""Please summarize this journaling conversation in 2-3 sentences, capturing the key themes, emotions, and insights discussed. Focus on what the user shared about their thoughts, feelings, or experiences.

Conversation:
{conversation_text}

Summary:"""
            
            # Generate summary using GPT
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise, empathetic summaries of journaling conversations."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Ensure summary is not too long
            if len(summary) > 200:
                summary = summary[:197] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Generate summary error: {str(e)}")
            # Fallback to a simple summary
            return self._create_fallback_summary(conversation_history)
    
    def _format_conversation_for_summary(self, conversation_history: List[Dict]) -> str:
        """
        Format conversation history for summarization
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            Formatted conversation text
        """
        formatted_lines = []
        
        for turn in conversation_history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            
            if role == "user":
                formatted_lines.append(f"User: {content}")
            elif role == "assistant":
                formatted_lines.append(f"Assistant: {content}")
        
        return "\n".join(formatted_lines)
    
    def _create_fallback_summary(self, conversation_history: List[Dict]) -> str:
        """
        Create a simple fallback summary if GPT fails
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            Simple summary string
        """
        user_messages = [
            turn["content"] for turn in conversation_history 
            if turn.get("role") == "user"
        ]
        
        if not user_messages:
            return "A journaling conversation was recorded."
        
        # Take the first user message as a simple summary
        first_message = user_messages[0]
        if len(first_message) > 100:
            return first_message[:97] + "..."
        
        return first_message
    
    def generate_title(self, conversation_history: List[Dict]) -> str:
        """
        Generate a title for the journal entry
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            Title string
        """
        try:
            # Get user messages
            user_messages = [
                turn["content"] for turn in conversation_history 
                if turn.get("role") == "user"
            ]
            
            if not user_messages:
                return "Journal Entry"
            
            # Use first user message to generate title
            first_message = user_messages[0]
            
            title_prompt = f"""Create a short, descriptive title (3-6 words) for this journal entry based on the user's opening message:

"{first_message}"

Title:"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates short, descriptive titles for journal entries."},
                    {"role": "user", "content": title_prompt}
                ],
                max_tokens=20,
                temperature=0.7
            )
            
            title = response.choices[0].message.content.strip()
            
            # Clean up title
            title = title.replace('"', '').replace("'", "").strip()
            
            return title if title else "Journal Entry"
            
        except Exception as e:
            logger.error(f"Generate title error: {str(e)}")
            return "Journal Entry"

# Global instance
summary_service = SummaryService()
