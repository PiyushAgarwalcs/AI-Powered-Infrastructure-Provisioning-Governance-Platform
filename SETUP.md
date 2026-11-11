# Setup Guide - RepoSage

## Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Internet connection (for GitHub API access)

## Quick Start (2 minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/AbhishekKharat04/repo-sage.git
cd repo-sage
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
python main.py
```

### 4. Open in Browser
Navigate to [http://localhost:8000](http://localhost:8000)

## Optional: IBM watsonx Configuration

For AI-powered analysis, you need IBM Cloud credentials:

### Get Your API Key
1. Go to [IBM Cloud](https://cloud.ibm.com)
2. Click your profile -> **Manage** -> **Access (IAM)**
3. Click **API keys** -> **Create an IBM Cloud API key**
4. Copy the key

### Get Your watsonx Project ID
1. Go to [watsonx.ai](https://dataplatform.cloud.ibm.com/wx/home)
2. Open your project
3. Click **Manage** tab -> find the Project ID

### Enter Credentials
In the RepoSage UI, enter your API key and Project ID in the optional credentials fields. The analysis will automatically use IBM watsonx Granite.

## Without IBM Credentials

RepoSage works perfectly without any API keys! It uses smart rule-based analysis that:
- Detects tech stacks from file extensions and content
- Identifies project architecture from folder structure
- Maps critical files using known patterns
- Assesses risk using code complexity heuristics

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Port 8000 in use | Change port in main.py: `uvicorn.run(..., port=8001)` |
| GitHub API rate limit | Wait 60 seconds or add a GitHub token |
| watsonx auth error | Verify your API key and Project ID |

---

*RepoSage - IBM Bob Hackathon 2026*

