# Google Drive Integration for Linear Visualizations

This document explains the new Google Drive integration feature for the Linear Issue Visualization API.

## Overview

The visualization endpoints now automatically upload generated images to Google Drive and return shareable links. This allows users to:
- Get persistent URLs for visualizations
- Share visualizations with others without authentication
- Access visualizations from anywhere
- Keep a history of generated visualizations in Google Drive

## Configuration

### Environment Variables

Create a `.env` file with the following configuration:

```bash
# Composio API Key
COMPOSIO_API_KEY=your_composio_api_key_here

# Linear Team ID
LINEAR_TEAM_ID=your_linear_team_id_here

# Google Drive Folder ID for uploads (required)
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here
```

### Composio Setup

The system uses Composio to handle Google Drive authentication.

To use your own Google Drive:
1. Sign up for Composio at https://composio.dev
2. Connect your Google Drive account
3. Set the `COMPOSIO_CONNECTED_ACCOUNT_ID` in your `.env` file

## Enhanced Endpoints

### 1. Timeline Visualization

**Endpoint:** `GET /visualize/timeline`

**Parameters:**
- `format`: `"png"` (generates image and uploads to Drive) or `"html"` (interactive)
- `filter_states`: Comma-separated list of states to filter (optional)

**Headers:**
- `X-API-Key`: Your API key

**Example Request:**
```bash
curl -X GET "http://localhost:8000/visualize/timeline?format=png" \
  -H "X-API-Key: $API_KEY"
```

**Response (PNG format):**
```json
{
  "status": "success",
  "shareable_link": "https://drive.google.com/file/d/1byQKRzR83VZHOpeCRiAS9YOEdxRXSsqw/view?usp=sharing",
  "file_id": "1byQKRzR83VZHOpeCRiAS9YOEdxRXSsqw",
  "filename": "linear_timeline_20251120_143022_a1b2c3d4.png",
  "message": "Visualization generated and uploaded successfully"
}
```

### 2. Statistics Visualization

**Endpoint:** `GET /visualize/stats`

**Parameters:**
- `format`: `"png"` (generates dashboard image) or `"json"` (raw data)

**Headers:**
- `X-API-Key`: Your API key

**Example Request:**
```bash
curl -X GET "http://localhost:8000/visualize/stats?format=png" \
  -H "X-API-Key: $API_KEY"
```

**Response (PNG format):**
```json
{
  "status": "success",
  "shareable_link": "https://drive.google.com/file/d/1xyz.../view?usp=sharing",
  "file_id": "1xyz...",
  "filename": "linear_stats_20251120_143125_e5f6g7h8.png",
  "message": "Statistics visualization generated and uploaded successfully",
  "stats_data": { ... }  // Includes the raw statistics data
}
```

## Generated Visualizations

### Timeline Visualization
- Shows issue state transitions over time
- Y-axis represents different states
- Each issue is shown as a connected line
- Includes transition time metrics
- Supports filtering by state

### Statistics Dashboard
- **State Distribution**: Pie chart showing current state distribution
- **Team Distribution**: Bar chart showing issues per team
- **Common Transitions**: Horizontal bar chart of top 10 state transitions
- **Transition Metrics**: Summary of average, min, and max times between states

## File Management

### Local Storage
- Images are temporarily saved to `./generated_images/` directory
- Files are automatically cleaned up after uploading to Google Drive
- Each file has a unique timestamp and ID to prevent conflicts

### Google Drive Organization
- All visualizations are uploaded to a specific folder in Google Drive
- Folder ID is configured via the `GOOGLE_DRIVE_FOLDER_ID` environment variable
- Files in the folder are named with timestamps for easy chronological sorting:
  - Timeline visualizations: `linear_timeline_YYYYMMDD_HHMMSS_uniqueid.png`
  - Statistics dashboards: `linear_stats_YYYYMMDD_HHMMSS_uniqueid.png`

## Testing

Run the included test script to verify the integration:

```bash
python test_visualization.py
```

This will:
1. Test timeline visualization generation
2. Test filtered timeline visualization
3. Test statistics JSON format
4. Test statistics PNG dashboard

## Shareable Links

The returned Google Drive links:
- Are publicly accessible (no authentication required)
- Can be shared via email, Slack, etc.
- Remain valid as long as the file exists in Google Drive
- Follow the format: `https://drive.google.com/file/d/{file_id}/view?usp=sharing`

## Error Handling

The system handles various error scenarios:
- Google Drive upload failures return 500 status with error details
- Missing API key returns 401 status
- Invalid format parameter returns 400 status
- No data available returns 404 status

## Security Notes

- API endpoints require authentication via X-API-Key header
- Google Drive uploads use Composio's secure OAuth integration
- Local files are deleted after successful upload
- File names include timestamps and UUIDs to ensure uniqueness
