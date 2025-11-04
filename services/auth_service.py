"""
Authentication service for Supabase auth integration
"""
from typing import Optional, Dict, Any
from supabase import Client
from services.supabase_client import supabase_client, get_supabase_client
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling user authentication"""
    
    def __init__(self, client: Client = None):
        self.client = client or supabase_client
    
    def _get_client(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Client:
        client = supabase_client
        if access_token and refresh_token:
            client.auth.set_session(access_token, refresh_token)
        return client
    
    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dict containing user data and session info
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session,
                    "message": "User registered successfully.  Please check your email to verify your account."
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create user"
                }
                
        except Exception as e:
            logger.error(f"Sign up error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in an existing user
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dict containing user data and session info
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session,
                    "message": "Signed in successfully."
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid credentials"
                }
                
        except Exception as e:
            logger.error(f"Sign in error: {str(e)}")
            return {
                "success": False,
                "error": "Invalid credentials"
            }
    
    def sign_out(self) -> Dict[str, Any]:
        """
        Sign out the current user
        
        Returns:
            Dict with success status
        """
        try:
            self.client.auth.sign_out()
            return {
                "success": True,
                "message": "Signed out successfully"
            }
        except Exception as e:
            logger.error(f"Sign out error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_current_user(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the currently authenticated user
        
        Args:
            access_token: Optional access token to use. If not provided, uses session.
            refresh_token: Optional refresh token (used for thread-local client).
        
        Returns:
            User data if authenticated, None otherwise
        """
        try:
            # Use thread-local client if tokens are provided
            client = self._get_client(access_token, refresh_token)
            response = client.auth.get_user(jwt=access_token)
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "created_at": response.user.created_at,
                    "updated_at": response.user.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            return None
    
    def set_session(self, access_token: str, refresh_token: str) -> bool:
        """
        Set the session with access and refresh tokens
        
        Args:
            access_token: The access token from Supabase
            refresh_token: The refresh token from Supabase
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.auth.set_session(access_token, refresh_token)
            return True
        except Exception as e:
            logger.error(f"Set session error: {str(e)}")
            return False
    
    def get_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the current session
        
        Returns:
            Session data if exists, None otherwise
        """
        try:
            response = self.client.auth.get_session()
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "user": response.session.user
                }
            return None
        except Exception as e:
            logger.error(f"Get session error: {str(e)}")
            return None

# Global instance
auth_service = AuthService()
