"""
Embedding service for OpenAI embeddings and vector storage
"""
from typing import List, Dict, Any, Tuple
import openai
import os
import logging
from supabase import Client
from services.supabase_client import supabase_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating and managing embeddings"""
    
    def __init__(self, client: Client = None):
        self.client = client or supabase_client
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
        # Initialize OpenAI client
        openai.api_key = self.api_key
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values
        """
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Generate embedding error: {str(e)}")
            raise e
    
    def chunk_conversation(self, conversation_history: List[Dict]) -> List[str]:
        """
        Split conversation into meaningful chunks for embedding
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            List of text chunks
        """
        chunks = []
        
        # Group consecutive user-assistant pairs
        current_chunk = ""
        for turn in conversation_history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            
            if role == "user":
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                current_chunk = f"User: {content}\n"
            elif role == "assistant":
                current_chunk += f"Assistant: {content}\n"
        
        # Add the last chunk if it exists
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If no chunks were created, create one from the entire conversation
        if not chunks:
            full_conversation = "\n".join([
                f"{turn.get('role', '').title()}: {turn.get('content', '')}"
                for turn in conversation_history
            ])
            chunks = [full_conversation]
        
        return chunks
    
    def store_embeddings(self, entry_id: str, user_id: str, chunks: List[str]) -> Dict[str, Any]:
        """
        Store embeddings for conversation chunks
        
        Args:
            entry_id: ID of the journal entry
            user_id: ID of the user
            chunks: List of text chunks
            
        Returns:
            Dict with success status
        """
        try:
            vectors_to_insert = []
            
            for chunk in chunks:
                # Generate embedding for this chunk
                embedding = self.generate_embedding(chunk)
                
                vectors_to_insert.append({
                    "entry_id": entry_id,
                    "user_id": user_id,
                    "chunk_text": chunk,
                    "embedding": embedding
                })
            
            # Insert all vectors at once
            response = self.client.table("journal_entry_vectors").insert(vectors_to_insert).execute()
            
            return {
                "success": True,
                "vectors_stored": len(response.data),
                "message": f"Stored {len(response.data)} embeddings"
            }
            
        except Exception as e:
            logger.error(f"Store embeddings error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_similar_entries(self, user_id: str, query_text: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search for similar entries using vector similarity
        
        Args:
            user_id: ID of the user
            query_text: Text to search for
            limit: Maximum number of results
            
        Returns:
            Dict containing similar entries
        """
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query_text)
            
            # Use Supabase's vector similarity search
            response = self.client.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter": {"user_id": user_id}
                }
            ).execute()
            
            return {
                "success": True,
                "results": response.data,
                "count": len(response.data)
            }
            
        except Exception as e:
            logger.error(f"Search similar entries error: {str(e)}")
            # Fallback to simple text search if vector search fails
            return self._fallback_text_search(user_id, query_text, limit)
    
    def _fallback_text_search(self, user_id: str, query_text: str, limit: int) -> Dict[str, Any]:
        """
        Fallback text search if vector search fails
        
        Args:
            user_id: ID of the user
            query_text: Text to search for
            limit: Maximum number of results
            
        Returns:
            Dict containing search results
        """
        try:
            # Simple text search in journal entries
            response = self.client.table("journal_entries")\
                .select("*")\
                .eq("user_id", user_id)\
                .ilike("summarized_text", f"%{query_text}%")\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            return {
                "success": True,
                "results": response.data,
                "count": len(response.data),
                "method": "text_search"
            }
            
        except Exception as e:
            logger.error(f"Fallback text search error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

# Global instance
embedding_service = EmbeddingService()
