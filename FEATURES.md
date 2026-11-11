# Features — RepoSage

## Core Analysis Engine

### 📖 Plain-English Summary
- Detects the tech stack (Python, JavaScript, TypeScript, Go, Java, Rust, etc.)
- Identifies the project type (Web App, API, CLI, Library)
- Generates an architecture diagram from the file tree
- Explains what the project does in simple terms

### 🚀 New Developer Onboarding Guide
- Identifies the entry point (main.py, index.js, etc.)
- Maps the data flow through the application
- Lists the top things to understand before touching code
- Warns about what NOT to modify as a beginner
- Provides local setup instructions

### 🗺️ Critical File Map
- Identifies the 5-8 most important files
- Labels each file with its role and priority level
- Uses a table format for quick scanning

### ⚠️ Danger Zones
- Flags high-risk files (config, auth, migrations)
- Identifies tightly coupled code areas
- Provides repo health indicators (tests, CI/CD, Docker, docs)

### 📝 Auto-Generated README
- Creates a professional README.md from code analysis
- Includes tech stack, project structure, getting started guide
- Formatted with proper markdown

## AI Modes

### IBM watsonx Granite (With API Key)
When IBM Cloud credentials are provided:
- Uses `ibm/granite-13b-instruct-v2` model
- Provides deeper, more contextual analysis
- Generates personalized onboarding recommendations
- Understands code patterns and relationships

### Smart Rule-Based Analysis (Without API Key)
When no credentials are provided:
- Detects 20+ programming languages and frameworks
- Identifies project types from file patterns
- Generates architecture diagrams automatically
- Uses heuristic-based risk assessment
- **Always works — no API key needed**

## Technical Features

- **Async file fetching** — concurrent GitHub API calls
- **Smart file filtering** — skips binaries, node_modules, build artifacts
- **Priority file ordering** — reads important files first
- **Graceful fallback** — if watsonx fails, switches to rule-based
- **Markdown rendering** — results displayed as rich formatted content
- **Copy-to-clipboard** — one-click copy for each section
- **Responsive design** — works on mobile and desktop

---

*RepoSage — IBM Bob Hackathon 2026*
