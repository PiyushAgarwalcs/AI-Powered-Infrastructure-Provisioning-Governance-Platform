"""
Session Management Module for ShipSage
Handles session creation, storage, and lifecycle management
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import asyncio
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Warning: redis not installed. Using in-memory storage.")


class SessionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


@dataclass
class Session:
    """Session data model"""
    id: str
    repo_url: str
    created_at: str
    expires_at: str
    owner_id: str
    analysis_data: dict
    configs: dict
    share_token: str
    is_public: bool
    status: str = SessionStatus.ACTIVE.value
    
    def to_dict(self) -> dict:
        """Convert session to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """Create session from dictionary"""
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > expires


class SessionManager:
    """Manages session storage and lifecycle"""
    
    def __init__(self, redis_url: Optional[str] = None, ttl_hours: int = 24):
        """
        Initialize session manager
        
        Args:
            redis_url: Redis connection URL (optional)
            ttl_hours: Session time-to-live in hours
        """
        self.ttl_hours = ttl_hours
        self.redis_client: Optional[redis.Redis] = None
        self.redis_url = redis_url
        
        # In-memory fallback storage
        self.memory_storage: Dict[str, Session] = {}
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize Redis connection if available"""
        if REDIS_AVAILABLE and self.redis_url:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self.redis_client.ping()
                print("✓ Connected to Redis for session storage")
            except Exception as e:
                print(f"⚠ Redis connection failed: {e}")
                print("  Using in-memory storage instead")
                self.redis_client = None
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def close(self):
        """Close Redis connection and cleanup"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return str(uuid.uuid4())
    
    def _generate_share_token(self) -> str:
        """Generate secure share token"""
        return str(uuid.uuid4()).replace('-', '')
    
    async def create_session(
        self,
        repo_url: str,
        owner_id: str,
        analysis_data: dict,
        configs: dict,
        is_public: bool = False
    ) -> Session:
        """
        Create a new session
        
        Args:
            repo_url: Repository URL
            owner_id: Session owner ID
            analysis_data: Analysis results
            configs: Generated configurations
            is_public: Whether session is publicly accessible
        
        Returns:
            Created session
        """
        session_id = self._generate_session_id()
        share_token = self._generate_share_token()
        
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.ttl_hours)
        
        session = Session(
            id=session_id,
            repo_url=repo_url,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            owner_id=owner_id,
            analysis_data=analysis_data,
            configs=configs,
            share_token=share_token,
            is_public=is_public,
            status=SessionStatus.ACTIVE.value
        )
        
        await self._save_session(session)
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID
        
        Args:
            session_id: Session ID
        
        Returns:
            Session if found, None otherwise
        """
        if self.redis_client:
            try:
                data = await self.redis_client.get(f"session:{session_id}")
                if data:
                    session = Session.from_dict(json.loads(data))
                    if session.is_expired():
                        await self.delete_session(session_id)
                        return None
                    return session
            except Exception as e:
                print(f"Error getting session from Redis: {e}")
        
        # Fallback to memory storage
        session = self.memory_storage.get(session_id)
        if session and session.is_expired():
            await self.delete_session(session_id)
            return None
        return session
    
    async def get_session_by_token(self, share_token: str) -> Optional[Session]:
        """
        Get session by share token
        
        Args:
            share_token: Share token
        
        Returns:
            Session if found, None otherwise
        """
        if self.redis_client:
            try:
                session_id = await self.redis_client.get(f"token:{share_token}")
                if session_id:
                    return await self.get_session(session_id)
            except Exception as e:
                print(f"Error getting session by token from Redis: {e}")
        
        # Fallback to memory storage
        for session in self.memory_storage.values():
            if session.share_token == share_token:
                if session.is_expired():
                    await self.delete_session(session.id)
                    return None
                return session
        return None
    
    async def update_session(
        self,
        session_id: str,
        analysis_data: Optional[dict] = None,
        configs: Optional[dict] = None
    ) -> Optional[Session]:
        """
        Update session data
        
        Args:
            session_id: Session ID
            analysis_data: Updated analysis data
            configs: Updated configurations
        
        Returns:
            Updated session if found, None otherwise
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        if analysis_data is not None:
            session.analysis_data = analysis_data
        if configs is not None:
            session.configs = configs
        
        await self._save_session(session)
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session
        
        Args:
            session_id: Session ID
        
        Returns:
            True if deleted, False otherwise
        """
        if self.redis_client:
            try:
                session = await self.get_session(session_id)
                if session:
                    # Delete token mapping
                    await self.redis_client.delete(f"token:{session.share_token}")
                    # Delete session
                    await self.redis_client.delete(f"session:{session_id}")
                    return True
            except Exception as e:
                print(f"Error deleting session from Redis: {e}")
        
        # Fallback to memory storage
        if session_id in self.memory_storage:
            del self.memory_storage[session_id]
            return True
        return False
    
    async def list_sessions(
        self,
        owner_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Session]:
        """
        List sessions
        
        Args:
            owner_id: Filter by owner ID
            limit: Maximum number of sessions to return
        
        Returns:
            List of sessions
        """
        sessions = []
        
        if self.redis_client:
            try:
                # Get all session keys
                keys = await self.redis_client.keys("session:*")
                for key in keys[:limit]:
                    data = await self.redis_client.get(key)
                    if data:
                        session = Session.from_dict(json.loads(data))
                        if owner_id is None or session.owner_id == owner_id:
                            if not session.is_expired():
                                sessions.append(session)
            except Exception as e:
                print(f"Error listing sessions from Redis: {e}")
        else:
            # Use memory storage
            for session in list(self.memory_storage.values())[:limit]:
                if owner_id is None or session.owner_id == owner_id:
                    if not session.is_expired():
                        sessions.append(session)
        
        return sessions
    
    async def _save_session(self, session: Session):
        """Save session to storage"""
        if self.redis_client:
            try:
                # Calculate TTL in seconds
                expires = datetime.fromisoformat(session.expires_at)
                ttl = int((expires - datetime.utcnow()).total_seconds())
                
                if ttl > 0:
                    # Save session
                    await self.redis_client.setex(
                        f"session:{session.id}",
                        ttl,
                        json.dumps(session.to_dict())
                    )
                    # Save token mapping
                    await self.redis_client.setex(
                        f"token:{session.share_token}",
                        ttl,
                        session.id
                    )
            except Exception as e:
                print(f"Error saving session to Redis: {e}")
                # Fallback to memory
                self.memory_storage[session.id] = session
        else:
            # Use memory storage
            self.memory_storage[session.id] = session
    
    async def _cleanup_expired_sessions(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                if not self.redis_client:
                    # Cleanup memory storage
                    expired_ids = [
                        sid for sid, session in self.memory_storage.items()
                        if session.is_expired()
                    ]
                    for sid in expired_ids:
                        del self.memory_storage[sid]
                    
                    if expired_ids:
                        print(f"Cleaned up {len(expired_ids)} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup task: {e}")


# Global session manager instance
session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global session_manager
    if session_manager is None:
        raise RuntimeError("Session manager not initialized")
    return session_manager


async def initialize_session_manager(redis_url: Optional[str] = None, ttl_hours: int = 24):
    """Initialize global session manager"""
    global session_manager
    session_manager = SessionManager(redis_url=redis_url, ttl_hours=ttl_hours)
    await session_manager.initialize()


async def close_session_manager():
    """Close global session manager"""
    global session_manager
    if session_manager:
        await session_manager.close()
        session_manager = None

# Made with Bob
