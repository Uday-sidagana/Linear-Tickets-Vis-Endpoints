# Linear Status Visualization

Track and visualize Linear issue state transitions over time.

## Core Files

- **main.py** - FastAPI server with webhook handler and visualization API
- **database.py** - SQLite database operations for issue state tracking
- **pastIssues.py** - Import existing Linear issues (run once for initial data)
- **requirements.txt** - Python dependencies
- **linear_issues.db** - SQLite database (created automatically)

## Setup

### Environment Configuration

1. Copy the environment template:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and configure your credentials:
   ```bash
   # Composio Configuration
   COMPOSIO_API_KEY=your_composio_api_key_here
   COMPOSIO_CONNECTED_ACCOUNT_ID=your_connected_account_id_here
   
   # API Authentication
   API_KEY=your_api_key_here
   
   # Google Drive Configuration
   GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here
   
   # Linear Configuration
   LINEAR_TEAM_ID=your_linear_team_id_here
   ```

### Installation

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Import existing issues (one-time):
   ```bash
   python pastIssues.py
   ```

4. Start the server:
   ```bash
   python main.py
   ```

5. Configure Linear webhooks to point to:
   ```
   http://your-server:8000/webhook
   ```

## API Endpoints

### Visualization (requires API key)
- `GET /visualize/timeline?format=html` - Interactive timeline with metrics
- `GET /visualize/timeline?format=png` - Static image with metrics
- `GET /visualize/stats` - Issue statistics and transition metrics

API Key: Set `API_KEY` in your `.env` file and use in `X-API-Key` header

Note: Timeline visualization only shows issues in these states:
- Agent Running (Y=0)
- Agent Change Needs Review (Y=1)
- In Master (Y=2)

**Transition Metrics**: Both timeline formats now display average time between state transitions:
- Average hours between each state transition
- Min/max times for each transition
- Number of times each transition occurred

Example:
```bash
# Get timeline with metrics
curl -X GET "http://localhost:8000/visualize/timeline?format=html" \
  -H "X-API-Key: $API_KEY" \
  --output timeline_with_metrics.html

# Get statistics including transition metrics
curl -X GET "http://localhost:8000/visualize/stats" \
  -H "X-API-Key: $API_KEY"
```

### Data Endpoints
- `GET /issues` - All issues with state history
- `GET /issues/{identifier}` - Specific issue history
- `GET /issues/state/{state}` - Issues by current state
