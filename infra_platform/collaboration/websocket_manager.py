"""
WebSocket Connection Manager for ShipSage
Handles real-time communication between clients
"""

import json
import asyncio
from typing import Dict, List, Set, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect


class MessageType(Enum):
    """WebSocket message types"""
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_TYPING = "user_typing"
    CURSOR_MOVE = "cursor_move"
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    COMMENT_RESOLVED = "comment_resolved"
    ANALYSIS_UPDATED = "analysis_updated"
    CONFIG_UPDATED = "config_updated"
    SESSION_UPDATED = "session_updated"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class User:
    """User information"""
    id: str
    username: str
    color: str
    joined_at: str
    last_seen: str
    cursor_position: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    type: str
    session_id: str
    user_id: str
    timestamp: str
    data: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(**data)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        """Initialize connection manager"""
        # session_id -> list of (websocket, user_id)
        self.active_connections: Dict[str, List[tuple[WebSocket, str]]] = {}
        
        # session_id -> user_id -> User
        self.session_users: Dict[str, Dict[str, User]] = {}
        
        # user_id -> websocket (for direct messaging)
        self.user_connections: Dict[str, WebSocket] = {}
        
        # Heartbeat task
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.heartbeat_interval = 30  # seconds
    
    def start_heartbeat(self):
        """Start heartbeat task"""
        if not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    def stop_heartbeat(self):
        """Stop heartbeat task"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
    
    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        username: str,
        color: str
    ):
        """
        Connect a new WebSocket client
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID
            user_id: User ID
            username: Username
            color: User color for UI
        """
        await websocket.accept()
        
        # Add to active connections
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append((websocket, user_id))
        
        # Add user to session
        if session_id not in self.session_users:
            self.session_users[session_id] = {}
        
        now = datetime.utcnow().isoformat()
        user = User(
            id=user_id,
            username=username,
            color=color,
            joined_at=now,
            last_seen=now
        )
        self.session_users[session_id][user_id] = user
        
        # Map user to websocket
        self.user_connections[user_id] = websocket
        
        # Notify others that user joined
        await self.broadcast(
            session_id,
            MessageType.USER_JOINED.value,
            user_id,
            {"user": user.to_dict()},
            exclude_user=user_id
        )
        
        # Send current session state to new user
        await self.send_personal(
            websocket,
            MessageType.SESSION_UPDATED.value,
            user_id,
            {
                "users": [u.to_dict() for u in self.session_users[session_id].values()],
                "connection_count": len(self.active_connections[session_id])
            }
        )
    
    async def disconnect(self, websocket: WebSocket, session_id: str, user_id: str):
        """
        Disconnect a WebSocket client
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID
            user_id: User ID
        """
        # Remove from active connections
        if session_id in self.active_connections:
            self.active_connections[session_id] = [
                (ws, uid) for ws, uid in self.active_connections[session_id]
                if ws != websocket
            ]
            
            # Clean up empty session
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        # Remove user from session
        if session_id in self.session_users:
            if user_id in self.session_users[session_id]:
                user = self.session_users[session_id][user_id]
                del self.session_users[session_id][user_id]
                
                # Notify others that user left
                await self.broadcast(
                    session_id,
                    MessageType.USER_LEFT.value,
                    user_id,
                    {"user": user.to_dict()}
                )
            
            # Clean up empty session
            if not self.session_users[session_id]:
                del self.session_users[session_id]
        
        # Remove user connection mapping
        if user_id in self.user_connections:
            del self.user_connections[user_id]
    
    async def broadcast(
        self,
        session_id: str,
        message_type: str,
        user_id: str,
        data: dict,
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast message to all clients in a session
        
        Args:
            session_id: Session ID
            message_type: Message type
            user_id: Sender user ID
            data: Message data
            exclude_user: User ID to exclude from broadcast
        """
        if session_id not in self.active_connections:
            return
        
        message = WebSocketMessage(
            type=message_type,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            data=data
        )
        
        # Send to all connections in session
        disconnected = []
        for websocket, uid in self.active_connections[session_id]:
            if exclude_user and uid == exclude_user:
                continue
            
            try:
                await websocket.send_text(message.to_json())
            except Exception as e:
                print(f"Error broadcasting to user {uid}: {e}")
                disconnected.append((websocket, uid))
        
        # Clean up disconnected clients
        for ws, uid in disconnected:
            await self.disconnect(ws, session_id, uid)
    
    async def send_personal(
        self,
        websocket: WebSocket,
        message_type: str,
        user_id: str,
        data: dict
    ):
        """
        Send message to a specific client
        
        Args:
            websocket: WebSocket connection
            message_type: Message type
            user_id: User ID
            data: Message data
        """
        message = WebSocketMessage(
            type=message_type,
            session_id="",  # Not needed for personal messages
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            data=data
        )
        
        try:
            await websocket.send_text(message.to_json())
        except Exception as e:
            print(f"Error sending personal message to user {user_id}: {e}")
    
    async def send_to_user(
        self,
        user_id: str,
        message_type: str,
        data: dict
    ):
        """
        Send message to a specific user by user ID
        
        Args:
            user_id: User ID
            message_type: Message type
            data: Message data
        """
        if user_id in self.user_connections:
            websocket = self.user_connections[user_id]
            await self.send_personal(websocket, message_type, user_id, data)
    
    def get_session_users(self, session_id: str) -> List[User]:
        """
        Get all users in a session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of users
        """
        if session_id in self.session_users:
            return list(self.session_users[session_id].values())
        return []
    
    def get_connection_count(self, session_id: str) -> int:
        """
        Get number of active connections in a session
        
        Args:
            session_id: Session ID
        
        Returns:
            Connection count
        """
        if session_id in self.active_connections:
            return len(self.active_connections[session_id])
        return 0
    
    def update_user_cursor(
        self,
        session_id: str,
        user_id: str,
        cursor_position: dict
    ):
        """
        Update user cursor position
        
        Args:
            session_id: Session ID
            user_id: User ID
            cursor_position: Cursor position data
        """
        if session_id in self.session_users:
            if user_id in self.session_users[session_id]:
                self.session_users[session_id][user_id].cursor_position = cursor_position
                self.session_users[session_id][user_id].last_seen = datetime.utcnow().isoformat()
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to all connections"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Send ping to all connections
                for session_id in list(self.active_connections.keys()):
                    disconnected = []
                    for websocket, user_id in self.active_connections[session_id]:
                        try:
                            await websocket.send_text(json.dumps({
                                "type": MessageType.PING.value,
                                "timestamp": datetime.utcnow().isoformat()
                            }))
                        except Exception as e:
                            print(f"Heartbeat failed for user {user_id}: {e}")
                            disconnected.append((websocket, user_id))
                    
                    # Clean up disconnected clients
                    for ws, uid in disconnected:
                        await self.disconnect(ws, session_id, uid)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in heartbeat loop: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager instance"""
    return connection_manager

# Made with Bob
