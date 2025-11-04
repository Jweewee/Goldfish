"""
Journal service for managing journal entries in Supabase
"""
from typing import List, Dict, Any, Optional
from supabase import Client
from services.supabase_client import supabase_client, get_supabase_client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class JournalService:
    """Service for managing journal entries"""
    
    def __init__(self, client: Client = None):
        self.client = client or supabase_client
    
    def _get_client(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Client:
        client = supabase_client
        if access_token and refresh_token:
            client.auth.set_session(access_token, refresh_token)
        return client
    
    def save_entry(self, user_id: str, conversation_history: List[Dict], summary: str, 
                   access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Save a journal entry
        
        Args:
            user_id: ID of the user
            conversation_history: List of conversation turns
            summary: Summary of the conversation
            access_token: Optional access token for thread-local client
            refresh_token: Optional refresh token for thread-local client
            
        Returns:
            Dict containing the saved entry data
        """
        try:
            client = self._get_client(access_token, refresh_token)
            # Convert conversation history to array of strings
            journal_interaction = []
            for turn in conversation_history:
                if turn.get("role") == "user":
                    journal_interaction.append(f"User: {turn.get('content', '')}")
                elif turn.get("role") == "assistant":
                    journal_interaction.append(f"Assistant: {turn.get('content', '')}")
            
            # Insert into journal_entries table
            response = client.table("journal_entries").insert({
                "user_id": user_id,
                "summarized_text": summary,
                "journal_interaction": journal_interaction,
                "timestamp": datetime.utcnow().isoformat()
            }).execute()
            
            if response.data:
                entry = response.data[0]
                return {
                    "success": True,
                    "entry": entry,
                    "message": "Entry saved successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save entry"
                }
                
        except Exception as e:
            logger.error(f"Save entry error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_entries(self, user_id: str, limit: int = 50, 
                         access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all journal entries for a user
        
        Args:
            user_id: ID of the user
            limit: Maximum number of entries to return
            access_token: Optional access token for thread-local client
            refresh_token: Optional refresh token for thread-local client
            
        Returns:
            Dict containing list of entries
        """
        try:
            client = self._get_client(access_token, refresh_token)
            response = client.table("journal_entries")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            return {
                "success": True,
                "entries": response.data,
                "count": len(response.data)
            }
            
        except Exception as e:
            logger.error(f"Get user entries error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "entries": []
            }
    
    def get_entry_by_id(self, entry_id: str, 
                         access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a specific journal entry by ID
        
        Args:
            entry_id: ID of the entry
            access_token: Optional access token for thread-local client
            refresh_token: Optional refresh token for thread-local client
            
        Returns:
            Dict containing the entry data
        """
        try:
            client = self._get_client(access_token, refresh_token)
            response = client.table("journal_entries")\
                .select("*")\
                .eq("id", entry_id)\
                .execute()
            
            if response.data:
                return {
                    "success": True,
                    "entry": response.data[0]
                }
            else:
                return {
                    "success": False,
                    "error": "Entry not found"
                }
                
        except Exception as e:
            logger.error(f"Get entry by ID error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_entry(self, entry_id: str, user_id: str,
                     access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a journal entry
        
        Args:
            entry_id: ID of the entry to delete
            user_id: ID of the user (for security)
            access_token: Optional access token for thread-local client
            refresh_token: Optional refresh token for thread-local client
            
        Returns:
            Dict with success status
        """
        try:
            client = self._get_client(access_token, refresh_token)
            # First delete associated vectors
            client.table("journal_entry_vectors")\
                .delete()\
                .eq("entry_id", entry_id)\
                .eq("user_id", user_id)\
                .execute()
            
            # Then delete the entry
            response = client.table("journal_entries")\
                .delete()\
                .eq("id", entry_id)\
                .eq("user_id", user_id)\
                .execute()
            
            return {
                "success": True,
                "message": "Entry deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Delete entry error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recent_entries(self, user_id: str, limit: int = 5,
                           access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get recent journal entries for dashboard
        
        Args:
            user_id: ID of the user
            limit: Number of recent entries to return
            access_token: Optional access token for thread-local client
            refresh_token: Optional refresh token for thread-local client
            
        Returns:
            Dict containing recent entries
        """
        try:
            client = self._get_client(access_token, refresh_token)
            response = client.table("journal_entries")\
                .select("id, summarized_text, timestamp")\
                .eq("user_id", user_id)\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            return {
                "success": True,
                "entries": response.data
            }
            
        except Exception as e:
            logger.error(f"Get recent entries error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "entries": []
            }

# Global instance
journal_service = JournalService()
