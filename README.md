# Jira AI Agent - Story & Test Case Generator

An intelligent system that automatically generates user stories and test cases from Jira epics or mock feature data using Google Gemini AI.

## 🚀 Features

- **AI-Powered Generation**: Uses Google Gemini 2.5 Flash for intelligent story and test case creation
- **Jira Integration**: Direct connection to Jira Cloud via REST API
- **Mock Data Support**: Upload JSON files for testing without Jira access
- **Multiple Export Formats**: JSON, CSV, and Markdown export options
- **Robust Fallbacks**: Template-based generation when AI is unavailable
- **Modern Web Interface**: Dark-themed, responsive UI with real-time updates

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## 🏃 Quick Start
Jira Assignment v1/
├── backend/
│   ├── app.py
│   ├── schema.py
│   ├── utils.py
│   └── requirement.txt
├── frontend/
│   ├── index.html
│   └── app.py
├── data/
│   └── mockdata.json


1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd "folder where you saved the code"
   ```

2. **Install dependencies**
   ```bash
   pip install -r backend/requirement.txt
   ```

3. **Set up environment variables**
   ```bash
   cd backend
   # Create .env file with your credentials (see Configuration section)
   ```

4. **Run the application**
   ```bash
   uvicorn app:app --reload --port 8000
   ```

5. **Open the web interface**
   - Navigate to `http://localhost:8000`
   - Open `frontend/index.html` in your browser

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Jira Cloud account (optional, for Jira integration)
- Google AI Studio account (optional, for AI features)

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.0 | Web framework for APIs |
| uvicorn | 0.30.6 | ASGI server |
| pydantic | 2.8.2 | Data validation |
| python-multipart | 0.0.9 | File upload support |
| httpx | 0.27.2 | HTTP client |
| python-dotenv | 1.0.1 | Environment management |
| google-generativeai | latest | Google Gemini AI SDK |

## ⚙️ Configuration

Create a `.env` file in the `backend` directory:

```env
# Jira Configuration (Required for Jira integration)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@domain.com
JIRA_API_TOKEN=your-api-token

# AI Configuration (Required for AI features)
GEMINI_API_KEY=your-gemini-api-key

# Optional: Server Configuration
PORT=8000
```

### Getting API Keys

#### Jira API Token
1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a label and copy the token

#### Google Gemini API Key
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to your `.env` file

## 🎯 Usage

### Web Interface

1. **Load Features**
   - **Option A**: Enter JQL query to fetch Jira epics
     ```
     project = YOURPROJECT AND issuetype = Epic ORDER BY created DESC
     ```
   - **Option B**: Upload a JSON file with mock feature data

2. **Generate Stories**
   - Click "Generate Stories" to create user stories from features
   - AI will generate stories with acceptance criteria and story points

3. **Generate Test Cases**
   - Click "Generate Tests" to create test cases for each story
   - Includes preconditions, steps, and expected outcomes

4. **Export Results**
   - Choose from JSON, CSV, or Markdown formats
   - Download files directly to your computer

### Sample Mock Data

Create a JSON file with this structure:

```json
[
  {
    "id": "F-001",
    "key": "EPIC-101",
    "title": "User Authentication",
    "description": "Implement secure user login, registration, and password reset functionality"
  },
  {
    "id": "F-002", 
    "key": "EPIC-102",
    "title": "Payment Processing",
    "description": "Enable customers to make payments using credit cards and digital wallets"
  }
]
```

## 📚 API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### Ingestion
- `POST /ingest/jira` - Fetch epics from Jira using JQL
- `POST /ingest/mock` - Upload mock feature data

#### Generation
- `POST /generate/stories` - Generate user stories from features
- `POST /generate/tests` - Generate test cases from stories

#### Export
- `GET /export?fmt=json` - Export as JSON
- `GET /export?fmt=csv` - Export as CSV
- `GET /export?fmt=md` - Export as Markdown

#### System
- `GET /` - Health check
- `GET /__env_check` - Environment configuration status
- `GET /__ai_engine` - AI engine status and errors
- `GET /__ai_status` - AI availability status

### Example API Calls

#### Fetch Jira Epics
```bash
curl -X POST "http://localhost:8000/ingest/jira" \
  -H "Content-Type: application/json" \
  -d '{"jql": "project = YOURPROJECT AND issuetype = Epic"}'
```

#### Generate Stories
```bash
curl -X POST "http://localhost:8000/generate/stories" \
  -H "Content-Type: application/json" \
  -d '{"features": [{"id": "F-001", "title": "Test Feature", "description": "Test Description"}]}'
```

## 🏗️ Project Structure

```
Jira Assignment v1/
├── backend/
│   ├── app.py              # Main FastAPI application
│   ├── schema.py           # Pydantic data models
│   ├── utils.py            # Utility functions and fallbacks
│   └── requirement.txt     # Python dependencies
├── frontend/
│   ├── app.py              # Frontend server (unused)
│   └── index.html          # Main web interface
├── data/
│   └── mockdata.json       # Sample feature data
├── ai/
│   └── __init__.py         # AI module placeholder
├── README.md               # This file
└── Jira Assignment Report.md # Detailed project report
```

## 🔧 Development

### Running in Development Mode

```bash
cd backend
uvicorn app:app --reload --port 8000
```

### Adding New Features

1. **Backend Changes**: Modify `backend/app.py` for new endpoints
2. **Frontend Changes**: Update `frontend/index.html` for UI modifications
3. **Data Models**: Update `backend/schema.py` for new data structures

### Testing

The system includes comprehensive fallback mechanisms:
- AI unavailable → Template-based generation
- Jira unavailable → Mock data upload
- Invalid input → Detailed error messages

## 🚨 Troubleshooting

### Common Issues

**"Missing API keys" Error**
- Ensure `.env` file exists in `backend/` directory
- Verify all required environment variables are set
- Check API key validity

**"Jira request failed" Error**
- Verify Jira URL format: `https://domain.atlassian.net`
- Check API token permissions
- Ensure JQL query syntax is correct

**"AI generation failed" Error**
- Verify Gemini API key is valid
- Check internet connection
- System will automatically fall back to templates

**Frontend not loading**
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify `frontend/index.html` is accessible

### Debug Mode

Enable debug logging by checking these endpoints:
- `GET /__env_check` - Environment status
- `GET /__ai_engine` - AI service status
- `GET /__ai_status` - AI availability

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Google Gemini AI](https://ai.google.dev/) for intelligent content generation
- [Atlassian Jira](https://www.atlassian.com/software/jira) for project management integration

## 📞 Support

For support, please:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [API Documentation](#api-documentation)
3. Open an issue on GitHub

---

**Made with ❤️ for Agile Development Teams**
