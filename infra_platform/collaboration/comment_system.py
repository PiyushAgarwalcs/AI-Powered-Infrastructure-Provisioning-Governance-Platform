"""
Comment System for ShipSage
Handles comments, threads, and discussions on analysis results
"""

import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
from enum import Enum


class CommentTargetType(Enum):
    """Types of targets that can be commented on"""
    FILE = "file"
    SECTION = "section"
    LINE = "line"
    CONFIG = "config"
    GENERAL = "general"


@dataclass
class Comment:
    """Comment data model"""
    id: str
    session_id: str
    user_id: str
    username: str
    target_type: str
    target_id: str
    content: str
    created_at: str
    updated_at: str
    resolved: bool = False
    parent_id: Optional[str] = None  # For threaded comments
    reactions: Dict[str, int] = None  # emoji -> count
    
    def __post_init__(self):
        if self.reactions is None:
            self.reactions = {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Comment':
        """Create from dictionary"""
        return cls(**data)


class CommentManager:
    """Manages comments and threads"""
    
    def __init__(self):
        """Initialize comment manager"""
        # In-memory storage: session_id -> list of comments
        self.comments: Dict[str, List[Comment]] = {}
        
        # Thread mapping: parent_id -> list of reply comment_ids
        self.threads: Dict[str, List[str]] = {}
    
    def _generate_comment_id(self) -> str:
        """Generate unique comment ID"""
        return str(uuid.uuid4())
    
    async def add_comment(
        self,
        session_id: str,
        user_id: str,
        username: str,
        target_type: str,
        target_id: str,
        content: str,
        parent_id: Optional[str] = None
    ) -> Comment:
        """
        Add a new comment
        
        Args:
            session_id: Session ID
            user_id: User ID
            username: Username
            target_type: Type of target (file, section, line, etc.)
            target_id: Target identifier
            content: Comment content
            parent_id: Parent comment ID for replies
        
        Returns:
            Created comment
        """
        comment_id = self._generate_comment_id()
        now = datetime.utcnow().isoformat()
        
        comment = Comment(
            id=comment_id,
            session_id=session_id,
            user_id=user_id,
            username=username,
            target_type=target_type,
            target_id=target_id,
            content=content,
            created_at=now,
            updated_at=now,
            resolved=False,
            parent_id=parent_id
        )
        
        # Add to storage
        if session_id not in self.comments:
            self.comments[session_id] = []
        self.comments[session_id].append(comment)
        
        # Update thread mapping
        if parent_id:
            if parent_id not in self.threads:
                self.threads[parent_id] = []
            self.threads[parent_id].append(comment_id)
        
        return comment
    
    async def get_comment(self, comment_id: str) -> Optional[Comment]:
        """
        Get comment by ID
        
        Args:
            comment_id: Comment ID
        
        Returns:
            Comment if found, None otherwise
        """
        for comments in self.comments.values():
            for comment in comments:
                if comment.id == comment_id:
                    return comment
        return None
    
    async def get_session_comments(
        self,
        session_id: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        include_replies: bool = True
    ) -> List[Comment]:
        """
        Get comments for a session
        
        Args:
            session_id: Session ID
            target_type: Filter by target type
            target_id: Filter by target ID
            resolved: Filter by resolved status
            include_replies: Include reply comments
        
        Returns:
            List of comments
        """
        if session_id not in self.comments:
            return []
        
        comments = self.comments[session_id]
        
        # Apply filters
        filtered = []
        for comment in comments:
            # Filter by target type
            if target_type and comment.target_type != target_type:
                continue
            
            # Filter by target ID
            if target_id and comment.target_id != target_id:
                continue
            
            # Filter by resolved status
            if resolved is not None and comment.resolved != resolved:
                continue
            
            # Filter replies if not included
            if not include_replies and comment.parent_id:
                continue
            
            filtered.append(comment)
        
        return filtered
    
    async def get_comment_thread(self, comment_id: str) -> List[Comment]:
        """
        Get comment thread (parent + all replies)
        
        Args:
            comment_id: Parent comment ID
        
        Returns:
            List of comments in thread
        """
        thread = []
        
        # Get parent comment
        parent = await self.get_comment(comment_id)
        if not parent:
            return []
        
        thread.append(parent)
        
        # Get replies
        if comment_id in self.threads:
            for reply_id in self.threads[comment_id]:
                reply = await self.get_comment(reply_id)
                if reply:
                    thread.append(reply)
        
        return thread
    
    async def update_comment(
        self,
        comment_id: str,
        content: Optional[str] = None,
        resolved: Optional[bool] = None
    ) -> Optional[Comment]:
        """
        Update comment
        
        Args:
            comment_id: Comment ID
            content: New content
            resolved: New resolved status
        
        Returns:
            Updated comment if found, None otherwise
        """
        comment = await self.get_comment(comment_id)
        if not comment:
            return None
        
        if content is not None:
            comment.content = content
        
        if resolved is not None:
            comment.resolved = resolved
        
        comment.updated_at = datetime.utcnow().isoformat()
        
        return comment
    
    async def delete_comment(self, comment_id: str) -> bool:
        """
        Delete comment and its replies
        
        Args:
            comment_id: Comment ID
        
        Returns:
            True if deleted, False otherwise
        """
        # Find and remove comment
        for session_id, comments in self.comments.items():
            for i, comment in enumerate(comments):
                if comment.id == comment_id:
                    # Remove comment
                    del comments[i]
                    
                    # Remove replies
                    if comment_id in self.threads:
                        reply_ids = self.threads[comment_id]
                        for reply_id in reply_ids:
                            await self.delete_comment(reply_id)
                        del self.threads[comment_id]
                    
                    return True
        
        return False
    
    async def resolve_comment(self, comment_id: str) -> Optional[Comment]:
        """
        Mark comment as resolved
        
        Args:
            comment_id: Comment ID
        
        Returns:
            Updated comment if found, None otherwise
        """
        return await self.update_comment(comment_id, resolved=True)
    
    async def unresolve_comment(self, comment_id: str) -> Optional[Comment]:
        """
        Mark comment as unresolved
        
        Args:
            comment_id: Comment ID
        
        Returns:
            Updated comment if found, None otherwise
        """
        return await self.update_comment(comment_id, resolved=False)
    
    async def add_reaction(
        self,
        comment_id: str,
        emoji: str
    ) -> Optional[Comment]:
        """
        Add reaction to comment
        
        Args:
            comment_id: Comment ID
            emoji: Emoji reaction
        
        Returns:
            Updated comment if found, None otherwise
        """
        comment = await self.get_comment(comment_id)
        if not comment:
            return None
        
        if emoji in comment.reactions:
            comment.reactions[emoji] += 1
        else:
            comment.reactions[emoji] = 1
        
        comment.updated_at = datetime.utcnow().isoformat()
        
        return comment
    
    async def remove_reaction(
        self,
        comment_id: str,
        emoji: str
    ) -> Optional[Comment]:
        """
        Remove reaction from comment
        
        Args:
            comment_id: Comment ID
            emoji: Emoji reaction
        
        Returns:
            Updated comment if found, None otherwise
        """
        comment = await self.get_comment(comment_id)
        if not comment:
            return None
        
        if emoji in comment.reactions:
            comment.reactions[emoji] -= 1
            if comment.reactions[emoji] <= 0:
                del comment.reactions[emoji]
        
        comment.updated_at = datetime.utcnow().isoformat()
        
        return comment
    
    async def get_comment_count(
        self,
        session_id: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        resolved: Optional[bool] = None
    ) -> int:
        """
        Get comment count for a session
        
        Args:
            session_id: Session ID
            target_type: Filter by target type
            target_id: Filter by target ID
            resolved: Filter by resolved status
        
        Returns:
            Comment count
        """
        comments = await self.get_session_comments(
            session_id,
            target_type=target_type,
            target_id=target_id,
            resolved=resolved,
            include_replies=True
        )
        return len(comments)
    
    async def get_unresolved_count(self, session_id: str) -> int:
        """
        Get count of unresolved comments
        
        Args:
            session_id: Session ID
        
        Returns:
            Unresolved comment count
        """
        return await self.get_comment_count(session_id, resolved=False)
    
    async def clear_session_comments(self, session_id: str):
        """
        Clear all comments for a session
        
        Args:
            session_id: Session ID
        """
        if session_id in self.comments:
            # Clear thread mappings
            for comment in self.comments[session_id]:
                if comment.id in self.threads:
                    del self.threads[comment.id]
            
            # Clear comments
            del self.comments[session_id]
    
    def get_statistics(self, session_id: str) -> dict:
        """
        Get comment statistics for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            Statistics dictionary
        """
        if session_id not in self.comments:
            return {
                "total": 0,
                "resolved": 0,
                "unresolved": 0,
                "threads": 0,
                "by_target_type": {}
            }
        
        comments = self.comments[session_id]
        
        total = len(comments)
        resolved = sum(1 for c in comments if c.resolved)
        unresolved = total - resolved
        threads = sum(1 for c in comments if not c.parent_id)
        
        by_target_type = {}
        for comment in comments:
            target_type = comment.target_type
            if target_type not in by_target_type:
                by_target_type[target_type] = 0
            by_target_type[target_type] += 1
        
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": unresolved,
            "threads": threads,
            "by_target_type": by_target_type
        }


# Global comment manager instance
comment_manager = CommentManager()


def get_comment_manager() -> CommentManager:
    """Get global comment manager instance"""
    return comment_manager

# Made with Bob
