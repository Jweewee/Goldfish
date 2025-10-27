"""
RAG (Retrieval-Augmented Generation) service for context retrieval
"""
from typing import List, Dict, Any, Optional
import logging
from services.embedding_service import embedding_service
from services.journal_service import journal_service

logger = logging.getLogger(__name__)

class RAGService:
    """Service for retrieval-augmented generation"""
    
    def __init__(self):
        self.embedding_service = embedding_service
        self.journal_service = journal_service
    
    def get_relevant_context(self, user_id: str, current_message: str, limit: int = 3) -> Dict[str, Any]:
        """
        Get relevant context from past entries for the current message
        
        Args:
            user_id: ID of the user
            current_message: Current user message
            limit: Maximum number of relevant entries to return
            
        Returns:
            Dict containing relevant context
        """
        try:
            # Search for similar entries using vector similarity
            search_result = self.embedding_service.search_similar_entries(
                user_id=user_id,
                query_text=current_message,
                limit=limit
            )

            logger.info(f"Search result: {search_result}")
            
            if search_result["success"] and search_result["results"]:
                # Format the context for the LLM
                formatted_context = self.format_context_for_prompt(search_result["results"])
                
                return {
                    "success": True,
                    "context": formatted_context,
                    "relevant_entries": search_result["results"],
                    "count": len(search_result["results"])
                }
            else:
                return {
                    "success": True,
                    "context": "",
                    "relevant_entries": [],
                    "count": 0
                }
                
        except Exception as e:
            logger.error(f"Get relevant context error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "context": "",
                "relevant_entries": []
            }
    
    def format_context_for_prompt(self, entries: List[Dict]) -> str:
        """
        Format retrieved entries for inclusion in the LLM prompt
        
        Args:
            entries: List of relevant journal entries
            
        Returns:
            Formatted context string
        """
        if not entries:
            return ""
        
        context_parts = []
        
        for entry in entries:
            # Extract content and timestamp from the vector search results
            content = entry.get("content", "")
            timestamp = entry.get("created_at", "")
            
            # Format timestamp for readability
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%B %d, %Y")
                except:
                    formatted_time = timestamp
            else:
                formatted_time = "Unknown date"
            
            context_parts.append(f"- {formatted_time}: {content}")
        
        if context_parts:
            context = "You previously discussed with this user:\n" + "\n".join(context_parts)
            context += "\n\nUse this context subtly and naturally in your response, but don't over-reference it."
            return context
        
        return ""
    
    def get_conversation_context(self, user_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """
        Get context based on the entire conversation history
        
        Args:
            user_id: ID of the user
            conversation_history: Current conversation history
            
        Returns:
            Dict containing context
        """
        try:
            # Extract key themes from conversation
            user_messages = [
                turn["content"] for turn in conversation_history 
                if turn.get("role") == "user"
            ]
            
            if not user_messages:
                return {"success": True, "context": "", "relevant_entries": []}
            
            # Use the most recent user message for context search
            latest_message = user_messages[-1]
            
            return self.get_relevant_context(user_id, latest_message)
            
        except Exception as e:
            logger.error(f"Get conversation context error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "context": "",
                "relevant_entries": []
            }
    
    def enhance_system_prompt(self, base_prompt: str, context: str) -> str:
        """
        Enhance the system prompt with retrieved context
        
        Args:
            base_prompt: Original system prompt
            context: Retrieved context
            
        Returns:
            Enhanced system prompt
        """
        if not context:
            return base_prompt
        
        # Add context section to the system prompt
        enhanced_prompt = base_prompt + "\n\n" + context
        
        return enhanced_prompt

# Global instance
rag_service = RAGService()
