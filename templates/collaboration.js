/**
 * ShipSage Phase 3: Real-time Collaboration Features
 * WebSocket client and collaboration UI
 */

class CollaborationManager {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.userId = null;
        this.username = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.isConnected = false;
        this.activeUsers = new Map();
        this.comments = [];
    }

    /**
     * Initialize collaboration for a session
     */
    async init(sessionId) {
        this.sessionId = sessionId;
        this.userId = this.generateUserId();
        this.username = this.generateUsername();
        
        // Connect to WebSocket
        await this.connect();
        
        // Load existing comments
        await this.loadComments();
        
        // Setup UI
        this.setupUI();
    }

    /**
     * Connect to WebSocket server
     */
    async connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;

        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('✓ WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.showNotification('Connected to collaboration session', 'success');
            };

            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showNotification('Connection error', 'error');
            };
        } catch (error) {
            console.error('Failed to connect:', error);
            this.attemptReconnect();
        }
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.showNotification('Failed to reconnect. Please refresh the page.', 'error');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(message) {
        const { type, user_id, data } = message;

        switch (type) {
            case 'user_joined':
                this.handleUserJoined(data.user);
                break;
            case 'user_left':
                this.handleUserLeft(data.user);
                break;
            case 'session_updated':
                this.handleSessionUpdated(data);
                break;
            case 'comment_added':
                this.handleCommentAdded(data.comment);
                break;
            case 'comment_updated':
                this.handleCommentUpdated(data.comment);
                break;
            case 'comment_deleted':
                this.handleCommentDeleted(data.comment_id);
                break;
            case 'comment_resolved':
                this.handleCommentResolved(data.comment);
                break;
            case 'cursor_move':
                this.handleCursorMove(user_id, data);
                break;
            case 'user_typing':
                this.handleUserTyping(user_id, data);
                break;
            case 'ping':
                this.sendPong();
                break;
        }
    }

    /**
     * Send message to WebSocket
     */
    send(type, data) {
        if (!this.isConnected || !this.ws) {
            console.warn('WebSocket not connected');
            return;
        }

        this.ws.send(JSON.stringify({
            type,
            session_id: this.sessionId,
            user_id: this.userId,
            data
        }));
    }

    /**
     * Send pong response
     */
    sendPong() {
        this.send('pong', {});
    }

    /**
     * Handle user joined
     */
    handleUserJoined(user) {
        this.activeUsers.set(user.id, user);
        this.updateUsersList();
        this.showNotification(`${user.username} joined`, 'info');
    }

    /**
     * Handle user left
     */
    handleUserLeft(user) {
        this.activeUsers.delete(user.id);
        this.updateUsersList();
        this.showNotification(`${user.username} left`, 'info');
    }

    /**
     * Handle session updated
     */
    handleSessionUpdated(data) {
        if (data.users) {
            this.activeUsers.clear();
            data.users.forEach(user => {
                this.activeUsers.set(user.id, user);
            });
            this.updateUsersList();
        }
    }

    /**
     * Handle comment added
     */
    handleCommentAdded(comment) {
        this.comments.push(comment);
        this.renderComments();
        if (comment.user_id !== this.userId) {
            this.showNotification(`New comment from ${comment.username}`, 'info');
        }
    }

    /**
     * Handle comment updated
     */
    handleCommentUpdated(comment) {
        const index = this.comments.findIndex(c => c.id === comment.id);
        if (index !== -1) {
            this.comments[index] = comment;
            this.renderComments();
        }
    }

    /**
     * Handle comment deleted
     */
    handleCommentDeleted(commentId) {
        this.comments = this.comments.filter(c => c.id !== commentId);
        this.renderComments();
    }

    /**
     * Handle comment resolved
     */
    handleCommentResolved(comment) {
        this.handleCommentUpdated(comment);
    }

    /**
     * Handle cursor move
     */
    handleCursorMove(userId, data) {
        // Update cursor position for user
        const user = this.activeUsers.get(userId);
        if (user) {
            user.cursor_position = data;
            // TODO: Render cursor on UI
        }
    }

    /**
     * Handle user typing
     */
    handleUserTyping(userId, data) {
        // Show typing indicator
        const user = this.activeUsers.get(userId);
        if (user) {
            this.showTypingIndicator(user.username);
        }
    }

    /**
     * Load existing comments from API
     */
    async loadComments() {
        try {
            const response = await fetch(`/api/sessions/${this.sessionId}/comments`);
            const data = await response.json();
            this.comments = data.comments || [];
            this.renderComments();
        } catch (error) {
            console.error('Failed to load comments:', error);
        }
    }

    /**
     * Add a new comment
     */
    async addComment(targetType, targetId, content, parentId = null) {
        try {
            const response = await fetch(`/api/sessions/${this.sessionId}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.userId,
                    username: this.username,
                    target_type: targetType,
                    target_id: targetId,
                    content,
                    parent_id: parentId
                })
            });
            
            if (!response.ok) throw new Error('Failed to add comment');
            
            const comment = await response.json();
            return comment;
        } catch (error) {
            console.error('Failed to add comment:', error);
            this.showNotification('Failed to add comment', 'error');
        }
    }

    /**
     * Resolve a comment
     */
    async resolveComment(commentId) {
        try {
            const response = await fetch(`/api/comments/${commentId}/resolve`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to resolve comment');
            
            return await response.json();
        } catch (error) {
            console.error('Failed to resolve comment:', error);
            this.showNotification('Failed to resolve comment', 'error');
        }
    }

    /**
     * Delete a comment
     */
    async deleteComment(commentId) {
        try {
            const response = await fetch(`/api/comments/${commentId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to delete comment');
            
            return true;
        } catch (error) {
            console.error('Failed to delete comment:', error);
            this.showNotification('Failed to delete comment', 'error');
        }
    }

    /**
     * Get share link
     */
    async getShareLink() {
        try {
            const response = await fetch(`/api/sessions/${this.sessionId}/share`);
            const data = await response.json();
            return data.share_url;
        } catch (error) {
            console.error('Failed to get share link:', error);
            return null;
        }
    }

    /**
     * Setup collaboration UI
     */
    setupUI() {
        // Add collaboration panel to sidebar
        this.addCollaborationPanel();
        
        // Add share button to topbar
        this.addShareButton();
        
        // Add comment button to configs
        this.addCommentButtons();
    }

    /**
     * Add collaboration panel to sidebar
     */
    addCollaborationPanel() {
        const navMenu = document.querySelector('.nav-menu');
        if (!navMenu) return;

        const collabSection = document.createElement('div');
        collabSection.innerHTML = `
            <div class="nav-section" style="margin-top: 20px;">Collaboration</div>
            <div class="nav-item" onclick="collaborationManager.toggleUsersPanel()">
                <i>👥</i>
                <span>Active Users (<span id="user-count">0</span>)</span>
            </div>
            <div class="nav-item" onclick="collaborationManager.toggleCommentsPanel()">
                <i>💬</i>
                <span>Comments (<span id="comment-count">0</span>)</span>
            </div>
        `;
        navMenu.appendChild(collabSection);

        // Add users panel
        this.createUsersPanel();
        
        // Add comments panel
        this.createCommentsPanel();
    }

    /**
     * Create users panel
     */
    createUsersPanel() {
        const panel = document.createElement('div');
        panel.id = 'users-panel';
        panel.className = 'collab-panel';
        panel.style.display = 'none';
        panel.innerHTML = `
            <div class="panel-header">
                <h3>Active Users</h3>
                <button onclick="collaborationManager.toggleUsersPanel()">✕</button>
            </div>
            <div id="users-list" class="panel-content"></div>
        `;
        document.body.appendChild(panel);
    }

    /**
     * Create comments panel
     */
    createCommentsPanel() {
        const panel = document.createElement('div');
        panel.id = 'comments-panel';
        panel.className = 'collab-panel';
        panel.style.display = 'none';
        panel.innerHTML = `
            <div class="panel-header">
                <h3>Comments</h3>
                <button onclick="collaborationManager.toggleCommentsPanel()">✕</button>
            </div>
            <div class="panel-content">
                <div class="comment-filters">
                    <button onclick="collaborationManager.filterComments('all')" class="active">All</button>
                    <button onclick="collaborationManager.filterComments('unresolved')">Unresolved</button>
                    <button onclick="collaborationManager.filterComments('resolved')">Resolved</button>
                </div>
                <div id="comments-list"></div>
                <div class="add-comment-form">
                    <textarea id="new-comment-text" placeholder="Add a comment..."></textarea>
                    <button onclick="collaborationManager.submitComment()">Post Comment</button>
                </div>
            </div>
        `;
        document.body.appendChild(panel);
    }

    /**
     * Add share button
     */
    addShareButton() {
        const topbarActions = document.querySelector('.topbar-actions');
        if (!topbarActions) return;

        const shareBtn = document.createElement('button');
        shareBtn.className = 'btn-outline';
        shareBtn.innerHTML = '🔗 Share';
        shareBtn.onclick = () => this.showShareDialog();
        topbarActions.insertBefore(shareBtn, topbarActions.firstChild);
    }

    /**
     * Add comment buttons to configs
     */
    addCommentButtons() {
        // Add comment buttons to each config section
        document.querySelectorAll('.code-container').forEach((container, index) => {
            const header = container.querySelector('.code-header');
            if (header) {
                const commentBtn = document.createElement('button');
                commentBtn.className = 'comment-btn';
                commentBtn.innerHTML = '💬';
                commentBtn.title = 'Add comment';
                commentBtn.onclick = () => this.showCommentDialog('config', `config-${index}`);
                header.appendChild(commentBtn);
            }
        });
    }

    /**
     * Toggle users panel
     */
    toggleUsersPanel() {
        const panel = document.getElementById('users-panel');
        if (panel) {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }
    }

    /**
     * Toggle comments panel
     */
    toggleCommentsPanel() {
        const panel = document.getElementById('comments-panel');
        if (panel) {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }
    }

    /**
     * Update users list
     */
    updateUsersList() {
        const usersList = document.getElementById('users-list');
        const userCount = document.getElementById('user-count');
        
        if (userCount) {
            userCount.textContent = this.activeUsers.size;
        }

        if (!usersList) return;

        usersList.innerHTML = Array.from(this.activeUsers.values())
            .map(user => `
                <div class="user-item">
                    <div class="user-avatar" style="background: ${user.color}">${user.username[0]}</div>
                    <div class="user-name">${user.username}</div>
                </div>
            `).join('');
    }

    /**
     * Render comments
     */
    renderComments() {
        const commentsList = document.getElementById('comments-list');
        const commentCount = document.getElementById('comment-count');
        
        if (commentCount) {
            commentCount.textContent = this.comments.length;
        }

        if (!commentsList) return;

        const filteredComments = this.getFilteredComments();
        
        commentsList.innerHTML = filteredComments
            .map(comment => this.renderComment(comment))
            .join('');
    }

    /**
     * Render single comment
     */
    renderComment(comment) {
        const isOwn = comment.user_id === this.userId;
        const resolvedClass = comment.resolved ? 'resolved' : '';
        
        return `
            <div class="comment-item ${resolvedClass}" data-comment-id="${comment.id}">
                <div class="comment-header">
                    <strong>${comment.username}</strong>
                    <span class="comment-time">${this.formatTime(comment.created_at)}</span>
                </div>
                <div class="comment-content">${this.escapeHtml(comment.content)}</div>
                <div class="comment-actions">
                    ${!comment.resolved ? `<button onclick="collaborationManager.resolveComment('${comment.id}')">✓ Resolve</button>` : ''}
                    ${isOwn ? `<button onclick="collaborationManager.deleteComment('${comment.id}')">🗑 Delete</button>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Get filtered comments
     */
    getFilteredComments() {
        const filter = this.currentFilter || 'all';
        
        if (filter === 'all') return this.comments;
        if (filter === 'resolved') return this.comments.filter(c => c.resolved);
        if (filter === 'unresolved') return this.comments.filter(c => !c.resolved);
        
        return this.comments;
    }

    /**
     * Filter comments
     */
    filterComments(filter) {
        this.currentFilter = filter;
        
        // Update active button
        document.querySelectorAll('.comment-filters button').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        this.renderComments();
    }

    /**
     * Submit comment
     */
    async submitComment() {
        const textarea = document.getElementById('new-comment-text');
        const content = textarea.value.trim();
        
        if (!content) return;
        
        await this.addComment('general', '', content);
        textarea.value = '';
    }

    /**
     * Show share dialog
     */
    async showShareDialog() {
        const shareUrl = await this.getShareLink();
        if (!shareUrl) return;

        const fullUrl = window.location.origin + shareUrl;
        
        // Copy to clipboard
        try {
            await navigator.clipboard.writeText(fullUrl);
            this.showNotification('Share link copied to clipboard!', 'success');
        } catch (error) {
            // Fallback: show dialog with link
            alert(`Share this link:\n\n${fullUrl}`);
        }
    }

    /**
     * Show comment dialog
     */
    showCommentDialog(targetType, targetId) {
        const content = prompt('Enter your comment:');
        if (content) {
            this.addComment(targetType, targetId, content);
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Show typing indicator
     */
    showTypingIndicator(username) {
        // TODO: Implement typing indicator
    }

    /**
     * Generate user ID
     */
    generateUserId() {
        return 'user-' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Generate username
     */
    generateUsername() {
        const adjectives = ['Quick', 'Smart', 'Clever', 'Swift', 'Bright'];
        const nouns = ['Fox', 'Eagle', 'Wolf', 'Hawk', 'Lion'];
        const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
        const noun = nouns[Math.floor(Math.random() * nouns.length)];
        return `${adj}${noun}${Math.floor(Math.random() * 100)}`;
    }

    /**
     * Format time
     */
    formatTime(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Disconnect
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
}

// Global instance
let collaborationManager = null;

// Initialize collaboration when session is available
function initCollaboration(sessionId) {
    if (!sessionId) return;
    
    collaborationManager = new CollaborationManager();
    collaborationManager.init(sessionId);
}

// Add CSS for collaboration UI
const collabStyles = document.createElement('style');
collabStyles.textContent = `
    .collab-panel {
        position: fixed;
        right: 20px;
        top: 90px;
        width: 350px;
        max-height: calc(100vh - 120px);
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 100;
        display: flex;
        flex-direction: column;
    }
    
    .panel-header {
        padding: 16px 20px;
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .panel-header h3 {
        font-size: 16px;
        font-weight: 700;
        margin: 0;
    }
    
    .panel-header button {
        background: none;
        border: none;
        color: var(--text-muted);
        font-size: 20px;
        cursor: pointer;
        padding: 0;
        width: 24px;
        height: 24px;
    }
    
    .panel-content {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
    }
    
    .user-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    
    .user-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 14px;
    }
    
    .user-name {
        font-size: 14px;
        font-weight: 500;
    }
    
    .comment-filters {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
    }
    
    .comment-filters button {
        flex: 1;
        padding: 6px 12px;
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 6px;
        color: var(--text);
        font-size: 12px;
        cursor: pointer;
        transition: 0.2s;
    }
    
    .comment-filters button.active {
        background: var(--primary);
        border-color: var(--primary);
        color: white;
    }
    
    .comment-item {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    }
    
    .comment-item.resolved {
        opacity: 0.6;
    }
    
    .comment-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-size: 13px;
    }
    
    .comment-time {
        color: var(--text-muted);
        font-size: 11px;
    }
    
    .comment-content {
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 8px;
    }
    
    .comment-actions {
        display: flex;
        gap: 8px;
    }
    
    .comment-actions button {
        padding: 4px 8px;
        background: transparent;
        border: 1px solid var(--border);
        border-radius: 4px;
        color: var(--text-muted);
        font-size: 11px;
        cursor: pointer;
        transition: 0.2s;
    }
    
    .comment-actions button:hover {
        border-color: var(--primary);
        color: var(--primary);
    }
    
    .add-comment-form {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
    }
    
    .add-comment-form textarea {
        width: 100%;
        min-height: 80px;
        padding: 12px;
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text);
        font-family: inherit;
        font-size: 14px;
        resize: vertical;
        margin-bottom: 8px;
    }
    
    .add-comment-form button {
        width: 100%;
        padding: 10px;
        background: var(--primary);
        border: none;
        border-radius: 6px;
        color: white;
        font-weight: 600;
        cursor: pointer;
        transition: 0.2s;
    }
    
    .add-comment-form button:hover {
        background: var(--primary-hover);
    }
    
    .comment-btn {
        margin-left: auto;
        background: transparent;
        border: none;
        color: var(--text-muted);
        font-size: 16px;
        cursor: pointer;
        padding: 4px 8px;
        transition: 0.2s;
    }
    
    .comment-btn:hover {
        color: var(--primary);
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(collabStyles);

// Made with Bob
