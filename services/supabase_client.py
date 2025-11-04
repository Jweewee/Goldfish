"""
Supabase client configuration and initialization
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Thread-local storage for Supabase clients
_client = None

def get_supabase_client() -> Client:
    """
    Get the shared Supabase client instance.
    """
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        _client = create_client(url, key)
    
    return _client

class SupabaseClient:
    """Singleton Supabase client instance (deprecated - use get_supabase_client instead)"""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseClient, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance
    
    def _initialize_client(self):
        """Initialize the Supabase client"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        
        self._client = create_client(url, key)
    
    @property
    def client(self) -> Client:
        """Get the Supabase client instance"""
        return self._client

# Global instance (for backward compatibility)
supabase_client = SupabaseClient().client
