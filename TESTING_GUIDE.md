# ShipSage - Comprehensive Testing Guide

## Overview

This guide provides step-by-step instructions for testing all features implemented across Phase 1, Phase 2, and Phase 3 of ShipSage.

---

## 🚀 Setup for Testing

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Start Redis for Phase 3 testing
docker run -d -p 6379:6379 redis:latest

# Set environment variables (optional)
export REDIS_URL=redis://localhost:6379
export BASE_URL=http://127.0.0.1:8000
```

### Start the Application
```bash
python main.py
```

The application should start at `http://127.0.0.1:8000`

---

## 📋 Phase 1: Foundation Features Testing

### Test 1: Basic Repository Analysis (Public Repo)

**Steps:**
1. Open `http://127.0.0.1:8000`
2. Enter a public GitHub repository URL (e.g., `https://github.com/facebook/react`)
3. Leave GitHub token empty
4. Select AI provider (or use rule-based)
5. Click "Analyze Repository"

**Expected Results:**
- ✅ Loading animation appears
- ✅ Analysis completes successfully
- ✅ Dashboard displays with metrics
- ✅ All configuration files generated
- ✅ No errors in console

**Success Criteria:**
- Analysis completes in < 30 seconds
- All 7 config types generated
- Readiness score displayed

---

### Test 2: Private Repository Analysis (With Token)

**Steps:**
1. Go to https://github.com/settings/tokens
2. Create a personal access token with `repo` scope
3. Copy the token
4. In ShipSage, enter a private repository URL
5. Paste the GitHub token
6. Click "Analyze Repository"

**Expected Results:**
- ✅ Token validated successfully
- ✅ Private repository accessed
- ✅ Analysis completes
- ✅ Rate limit increased (5000/hr vs 60/hr)

**Success Criteria:**
- Private repo analyzed successfully
- No authentication errors
- Token stored securely (not logged)

---

### Test 3: ZIP Export Functionality

**Steps:**
1. Complete any repository analysis
2. Click "Download All" button in topbar
3. Wait for ZIP download

**Expected Results:**
- ✅ ZIP file downloads automatically
- ✅ Filename format: `shipsage-{repo-name}.zip`
- ✅ ZIP contains all configs
- ✅ Organized directory structure
- ✅ README and ANALYSIS files included

**Success Criteria:**
- ZIP downloads in < 2 seconds
- All 7 config files present
- Files are properly formatted
- README contains instructions

**Verify ZIP Contents:**
```
shipsage-{repo}/
├── README.md
├── ANALYSIS.md
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── kubernetes/
│   └── deployment.yaml
├── cicd/
│   └── github-actions.yml
├── terraform/
│   └── main.tf
├── monitoring/
│   └── prometheus.yml
└── config/
    ├── .env.example
    └── nginx.conf
```

---

### Test 4: CI/CD Pipeline (GitHub Actions)

**Note:** This test requires pushing to a GitHub repository.

**Steps:**
1. Fork the ShipSage repository
2. Enable GitHub Actions
3. Push a commit to main branch
4. Check Actions tab

**Expected Results:**
- ✅ Workflow triggers automatically
- ✅ All 4 stages complete successfully:
  - Lint & Test
  - Build Docker Image
  - Push to Docker Hub
  - Deploy (if configured)

**Success Criteria:**
- Pipeline completes in < 8 minutes
- Docker image pushed to registry
- No failed steps
- Green checkmark on commit

---

## 📋 Phase 2: Intelligence Features Testing

### Test 5: Multi-AI Provider Integration

#### Test 5a: IBM watsonx Provider

**Steps:**
1. Get watsonx API key and project ID
2. In setup form, select "IBM watsonx Granite"
3. Enter API key and project ID
4. Analyze a repository

**Expected Results:**
- ✅ AI provider selected
- ✅ Credentials validated
- ✅ AI-powered analysis runs
- ✅ Badge shows "IBM watsonx Active"
- ✅ Enhanced recommendations

**Success Criteria:**
- AI analysis completes
- Recommendations are detailed
- No API errors

#### Test 5b: OpenAI Provider

**Steps:**
1. Get OpenAI API key
2. Select "OpenAI GPT-4"
3. Enter API key
4. Analyze repository

**Expected Results:**
- ✅ OpenAI API called successfully
- ✅ GPT-4 analysis provided
- ✅ Detailed insights generated

#### Test 5c: Anthropic Claude Provider

**Steps:**
1. Get Anthropic API key
2. Select "Anthropic Claude"
3. Enter API key
4. Analyze repository

**Expected Results:**
- ✅ Claude API called successfully
- ✅ Analysis completed
- ✅ Recommendations provided

#### Test 5d: Ollama (Local) Provider

**Prerequisites:**
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3
```

**Steps:**
1. Select "Ollama (Local)"
2. Enter model name (e.g., "llama3")
3. Enter endpoint (default: http://localhost:11434)
4. Analyze repository

**Expected Results:**
- ✅ Connects to local Ollama
- ✅ Model inference runs
- ✅ Analysis completes offline

#### Test 5e: Rule-based Provider (Fallback)

**Steps:**
1. Select "Rule-based (No AI)"
2. Analyze repository

**Expected Results:**
- ✅ Analysis completes without AI
- ✅ Smart rules applied
- ✅ Configs generated correctly
- ✅ Badge shows "Smart Rule Generation"

**Success Criteria:**
- All 5 providers work correctly
- Graceful fallback if AI fails
- Credentials handled securely

---

### Test 6: AWS Cost Estimation

#### Test 6a: Cost Estimation from Terraform

**Steps:**
1. Analyze a repository with Terraform configs
2. Navigate to "Cost Estimate" in sidebar
3. Review cost breakdown

**Expected Results:**
- ✅ Monthly total displayed
- ✅ Service-by-service breakdown
- ✅ Progress bars for each service
- ✅ Warnings displayed (if any)
- ✅ Optimization tips shown

**Verify Cost Components:**
- EKS cluster costs
- RDS database costs
- DocumentDB costs
- ECR costs
- S3 costs
- NAT Gateway costs
- Load Balancer costs
- Data transfer costs

#### Test 6b: Simple Cost Estimation

**Steps:**
1. Analyze a repository without Terraform
2. Check cost estimate
3. Verify simple estimation used

**Expected Results:**
- ✅ Basic cost estimate provided
- ✅ Based on detected stack
- ✅ Database costs included if detected

**Success Criteria:**
- Cost estimates are reasonable
- All AWS services accounted for
- Warnings for high costs
- Optimization tips relevant

---

## 📋 Phase 3: Collaboration Features Testing

### Test 7: Session Management

#### Test 7a: Session Creation

**Steps:**
1. Analyze any repository
2. Check response for session data
3. Verify session created

**Expected Results:**
- ✅ `session_id` in response
- ✅ `share_token` generated
- ✅ `share_url` provided
- ✅ Session stored (Redis or memory)

**Verify via API:**
```bash
# Get session details
curl http://127.0.0.1:8000/api/sessions/{session_id}
```

#### Test 7b: Session Retrieval

**Steps:**
1. Use session ID from previous test
2. Call GET /api/sessions/{session_id}
3. Verify data returned

**Expected Results:**
- ✅ Session data retrieved
- ✅ Analysis data present
- ✅ Configs included
- ✅ Expiration time set

#### Test 7c: Session Expiration

**Steps:**
1. Create a session
2. Wait 24 hours (or modify TTL for testing)
3. Try to retrieve session

**Expected Results:**
- ✅ Session expires after TTL
- ✅ Returns 404 after expiration
- ✅ Cleanup task removes expired sessions

---

### Test 8: WebSocket Real-time Communication

#### Test 8a: WebSocket Connection

**Steps:**
1. Analyze a repository
2. Open browser DevTools > Network > WS
3. Verify WebSocket connection

**Expected Results:**
- ✅ WebSocket connects to `/ws/{session_id}`
- ✅ Connection status: "Connected"
- ✅ User joined message received
- ✅ Session state message received

**Verify in Console:**
```javascript
// Should see:
✓ WebSocket connected
Connected to collaboration session
```

#### Test 8b: User Presence

**Steps:**
1. Open session in two browser tabs
2. Check "Active Users" panel
3. Verify both users shown

**Expected Results:**
- ✅ User count shows 2
- ✅ Both users listed with avatars
- ✅ Different colors assigned
- ✅ Usernames displayed

#### Test 8c: Heartbeat Mechanism

**Steps:**
1. Connect to session
2. Monitor WebSocket messages
3. Wait 30 seconds

**Expected Results:**
- ✅ PING messages sent every 30 seconds
- ✅ PONG responses sent back
- ✅ Connection stays alive

#### Test 8d: Reconnection

**Steps:**
1. Connect to session
2. Disable network temporarily
3. Re-enable network

**Expected Results:**
- ✅ Disconnection detected
- ✅ Reconnection attempts start
- ✅ Successfully reconnects
- ✅ Notification shown
- ✅ Max 5 attempts

---

### Test 9: Comment System

#### Test 9a: Add Comment

**Steps:**
1. Join a session
2. Click 💬 button on a config
3. Enter comment text
4. Submit

**Expected Results:**
- ✅ Comment saved to backend
- ✅ Comment appears in UI
- ✅ Other users see comment instantly
- ✅ Notification shown

**Verify via API:**
```bash
# List comments
curl http://127.0.0.1:8000/api/sessions/{session_id}/comments
```

#### Test 9b: Threaded Comments (Replies)

**Steps:**
1. Add a comment
2. Reply to the comment
3. Verify thread structure

**Expected Results:**
- ✅ Reply linked to parent
- ✅ Thread displayed correctly
- ✅ Parent-child relationship maintained

#### Test 9c: Resolve Comment

**Steps:**
1. Add a comment
2. Click "Resolve" button
3. Verify status

**Expected Results:**
- ✅ Comment marked as resolved
- ✅ Visual indicator shown (opacity)
- ✅ Other users see resolved status
- ✅ Can unresolve

#### Test 9d: Delete Comment

**Steps:**
1. Add a comment
2. Click "Delete" button
3. Confirm deletion

**Expected Results:**
- ✅ Comment removed from UI
- ✅ Removed from backend
- ✅ Other users see deletion
- ✅ Replies also deleted (cascade)

#### Test 9e: Comment Filtering

**Steps:**
1. Add multiple comments
2. Resolve some comments
3. Test filters: All / Resolved / Unresolved

**Expected Results:**
- ✅ "All" shows all comments
- ✅ "Resolved" shows only resolved
- ✅ "Unresolved" shows only unresolved
- ✅ Count updates correctly

#### Test 9f: Comment Statistics

**Steps:**
1. Add various comments
2. Call stats API endpoint

**Expected Results:**
- ✅ Total count correct
- ✅ Resolved count correct
- ✅ Unresolved count correct
- ✅ Thread count correct
- ✅ By target type breakdown

**Verify via API:**
```bash
curl http://127.0.0.1:8000/api/sessions/{session_id}/stats
```

---

### Test 10: Share Links

#### Test 10a: Generate Share Link

**Steps:**
1. Complete analysis
2. Click "Share" button
3. Verify link copied

**Expected Results:**
- ✅ Share link generated
- ✅ Copied to clipboard
- ✅ Notification shown
- ✅ Link format: `/session/{id}?token={token}`

#### Test 10b: Access via Share Link

**Steps:**
1. Copy share link
2. Open in new browser/incognito
3. Verify access

**Expected Results:**
- ✅ Session loads successfully
- ✅ Analysis data displayed
- ✅ Can view all configs
- ✅ Can add comments
- ✅ Real-time updates work

#### Test 10c: Share Link Expiration

**Steps:**
1. Generate share link
2. Wait for session expiration
3. Try to access link

**Expected Results:**
- ✅ Link expires with session
- ✅ Returns 404 or error
- ✅ Appropriate error message

---

## 🧪 Integration Testing

### Test 11: End-to-End Workflow

**Complete User Journey:**

1. **Setup**
   - Open ShipSage
   - Enter repository URL
   - Select AI provider
   - Enter credentials

2. **Analysis**
   - Click "Analyze Repository"
   - Wait for completion
   - Verify all metrics

3. **Review Configs**
   - Navigate through all config tabs
   - Verify syntax highlighting
   - Check completeness

4. **Cost Estimation**
   - View cost estimate
   - Review breakdown
   - Check warnings

5. **Collaboration**
   - Share link with team
   - Add comments
   - Resolve discussions

6. **Export**
   - Download ZIP
   - Verify contents
   - Extract and review

**Expected Results:**
- ✅ Entire workflow completes smoothly
- ✅ No errors at any step
- ✅ All features work together
- ✅ Data persists correctly

---

## 🔍 Performance Testing

### Test 12: Load Testing

#### Test 12a: Concurrent Users

**Tools:** Apache Bench, k6, or similar

**Steps:**
```bash
# Test 100 concurrent connections
ab -n 1000 -c 100 http://127.0.0.1:8000/

# Test WebSocket connections
# Use custom script to open 100 WebSocket connections
```

**Expected Results:**
- ✅ Handles 100+ concurrent users
- ✅ Response time < 2 seconds
- ✅ No connection drops
- ✅ Memory usage stable

#### Test 12b: Large Repository Analysis

**Steps:**
1. Analyze a large repository (1000+ files)
2. Monitor performance
3. Check completion time

**Expected Results:**
- ✅ Completes within reasonable time
- ✅ No memory leaks
- ✅ Progress updates shown
- ✅ All files processed

#### Test 12c: WebSocket Message Throughput

**Steps:**
1. Connect multiple clients
2. Send rapid messages
3. Measure delivery time

**Expected Results:**
- ✅ Messages delivered < 100ms
- ✅ No message loss
- ✅ Order preserved
- ✅ Broadcast efficient

---

## 🔒 Security Testing

### Test 13: Security Checks

#### Test 13a: Input Validation

**Steps:**
1. Try invalid repository URLs
2. Try SQL injection in inputs
3. Try XSS in comments

**Expected Results:**
- ✅ Invalid URLs rejected
- ✅ SQL injection prevented
- ✅ XSS sanitized
- ✅ Appropriate error messages

#### Test 13b: Token Security

**Steps:**
1. Enter GitHub token
2. Check network requests
3. Verify token not logged

**Expected Results:**
- ✅ Token sent securely
- ✅ Not logged in console
- ✅ Not exposed in responses
- ✅ HTTPS recommended

#### Test 13c: Session Security

**Steps:**
1. Try to access session without token
2. Try to modify other user's comments
3. Verify ownership checks

**Expected Results:**
- ✅ Unauthorized access blocked
- ✅ Ownership verified
- ✅ Proper error codes (401, 403)

---

## 📊 Test Results Template

### Test Execution Checklist

```markdown
## Phase 1 Tests
- [ ] Test 1: Basic Repository Analysis
- [ ] Test 2: Private Repository Analysis
- [ ] Test 3: ZIP Export
- [ ] Test 4: CI/CD Pipeline

## Phase 2 Tests
- [ ] Test 5a: watsonx Provider
- [ ] Test 5b: OpenAI Provider
- [ ] Test 5c: Anthropic Provider
- [ ] Test 5d: Ollama Provider
- [ ] Test 5e: Rule-based Provider
- [ ] Test 6a: Terraform Cost Estimation
- [ ] Test 6b: Simple Cost Estimation

## Phase 3 Tests
- [ ] Test 7a: Session Creation
- [ ] Test 7b: Session Retrieval
- [ ] Test 7c: Session Expiration
- [ ] Test 8a: WebSocket Connection
- [ ] Test 8b: User Presence
- [ ] Test 8c: Heartbeat
- [ ] Test 8d: Reconnection
- [ ] Test 9a: Add Comment
- [ ] Test 9b: Threaded Comments
- [ ] Test 9c: Resolve Comment
- [ ] Test 9d: Delete Comment
- [ ] Test 9e: Comment Filtering
- [ ] Test 9f: Comment Statistics
- [ ] Test 10a: Generate Share Link
- [ ] Test 10b: Access via Share Link
- [ ] Test 10c: Share Link Expiration

## Integration Tests
- [ ] Test 11: End-to-End Workflow

## Performance Tests
- [ ] Test 12a: Concurrent Users
- [ ] Test 12b: Large Repository
- [ ] Test 12c: Message Throughput

## Security Tests
- [ ] Test 13a: Input Validation
- [ ] Test 13b: Token Security
- [ ] Test 13c: Session Security
```

---

## 🐛 Bug Reporting Template

```markdown
### Bug Report

**Test Case:** Test X - Feature Name

**Environment:**
- OS: Windows/Mac/Linux
- Browser: Chrome/Firefox/Safari
- Python Version: 3.x
- Redis: Yes/No

**Steps to Reproduce:**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happened

**Screenshots/Logs:**
Attach relevant screenshots or error logs

**Severity:**
- [ ] Critical (blocks testing)
- [ ] High (major feature broken)
- [ ] Medium (feature partially works)
- [ ] Low (minor issue)
```

---

## ✅ Test Sign-off

### Acceptance Criteria

**Phase 1:**
- [ ] All basic features work
- [ ] Private repos accessible
- [ ] ZIP export functional
- [ ] CI/CD pipeline runs

**Phase 2:**
- [ ] All 5 AI providers work
- [ ] Cost estimation accurate
- [ ] Fallback mechanisms work

**Phase 3:**
- [ ] WebSocket connections stable
- [ ] Comments system functional
- [ ] Share links work
- [ ] Real-time sync working

**Overall:**
- [ ] No critical bugs
- [ ] Performance acceptable
- [ ] Security validated
- [ ] Documentation complete

---

## 📞 Support

For testing issues:
1. Check error logs in console
2. Verify environment setup
3. Review documentation
4. Report bugs using template above

**Happy Testing!** 🚀