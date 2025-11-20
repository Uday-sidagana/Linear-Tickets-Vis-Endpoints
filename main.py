import hmac
import hashlib
import base64
import time
import json
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from typing import Optional, List, Dict
import io
import os
import uvicorn
from database import IssueDatabase
from composio import Composio
from datetime import datetime as dt
import uuid

def verify_service_webhook(payload: str, signature_header: str, secret: str, msg_id: str, timestamp: int = None) -> bool:
    """
    Verify the service webhook signature
    
    Args:
        payload: Raw webhook payload as string
        signature_header: Value from webhook-signature header
        secret: Webhook secret from the service dashboard
        msg_id: Value from webhook-id header
        timestamp: Unix timestamp from webhook-timestamp header
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    # Parse signature (format: "v1,{base64_signature}")
    if not signature_header.startswith('v1,'):
        return False
    
    received_signature = signature_header[3:]
    
    # Create signing string: {msgId}.{timestamp}.{payload}
    signing_string = f"{msg_id}.{timestamp}.{payload}"
    
    # Generate expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    expected_signature_b64 = base64.b64encode(expected_signature).decode('utf-8')
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(received_signature, expected_signature_b64)

app = FastAPI()

# Initialize database
db = IssueDatabase()

# Initialize Composio
composio = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

def upload_to_google_drive_and_get_link(file_path: str, filename: str = None, folder_id: str = None) -> dict:
    """
    Upload a file to Google Drive and return a shareable link
    
    Args:
        file_path: Path to the file to upload
        filename: Optional custom filename for the uploaded file
        folder_id: Optional Google Drive folder ID to upload to (defaults to GOOGLE_DRIVE_FOLDER_ID env var)
        
    Returns:
        dict containing the shareable link and file ID
    """
    try:
        # If no filename provided, use the original filename
        if not filename:
            filename = os.path.basename(file_path)
        
        # Get folder ID from environment variable
        if not folder_id:
            folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
            if not folder_id:
                raise ValueError("GOOGLE_DRIVE_FOLDER_ID environment variable is required")
        
        # Build arguments
        upload_args = {
            "file_to_upload": file_path,
            "folder_to_upload_to": folder_id
        }
        
        # Execute the Google Drive upload
        # Get user ID and connected account ID from environment
        composio_user_id = os.getenv("COMPOSIO_USER_ID")
        if not composio_user_id:
            raise ValueError("COMPOSIO_USER_ID environment variable is required")
        
        composio_connected_account_id = os.getenv("COMPOSIO_GDRIVE_CONNECTED_ACCOUNT_ID")
        if not composio_connected_account_id:
            raise ValueError("COMPOSIO_GDRIVE_CONNECTED_ACCOUNT_ID environment variable is required")
        
        res = composio.tools.execute(
            "GOOGLEDRIVE_UPLOAD_FILE",
            user_id=composio_user_id,
            version="20251119_00",
            connected_account_id=composio_connected_account_id,
            arguments=upload_args
        )
        
        if res['successful'] and res['data']:
            file_id = res['data']['id']
            # Construct shareable link
            shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            
            return {
                "success": True,
                "file_id": file_id,
                "shareable_link": shareable_link,
                "filename": res['data']['name']
            }
        else:
            return {
                "success": False,
                "error": res.get('error', 'Unknown error during upload')
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Handle incoming webhook requests"""
    raw_payload = await request.body()
    payload_str = raw_payload.decode('utf-8')
    
    # Extract verification headers
    signature_header = request.headers.get("webhook-signature")
    msg_id = request.headers.get("webhook-id")
    timestamp_str = request.headers.get("webhook-timestamp")
    
    # Your webhook secret from the service dashboard
    webhook_secret = "cfbab4c0-be90-436d-9711-a542836661a7"
    
    # Verify the webhook signature
    if not verify_service_webhook(
        payload=payload_str,
        signature_header=signature_header,
        secret=webhook_secret,
        msg_id=msg_id,
        timestamp=int(timestamp_str) if timestamp_str else None
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process the webhook data
    webhook_data = json.loads(payload_str)
    print(f"Received webhook: {webhook_data}")
    
    # Extract the action type and issue data
    try:
        action = webhook_data['data']['action']
        issue_data = webhook_data['data']['data']
        
        if action == 'create':
            # Handle issue creation
            success = db.create_issue(issue_data)
            if success:
                return {
                    "status": "success", 
                    "message": f"Issue {issue_data['identifier']} created",
                    "action": "created"
                }
            else:
                return {
                    "status": "info",
                    "message": f"Issue {issue_data['identifier']} already exists",
                    "action": "skipped"
                }
                
        elif action == 'update':
            # Handle issue update
            success = db.update_issue_state(issue_data)
            if success:
                return {
                    "status": "success",
                    "message": f"Issue {issue_data['identifier']} state updated",
                    "action": "updated"
                }
            else:
                return {
                    "status": "info",
                    "message": f"Issue {issue_data['identifier']} state unchanged",
                    "action": "skipped"
                }
        else:
            return {
                "status": "info",
                "message": f"Unhandled action type: {action}",
                "action": "ignored"
            }
            
    except KeyError as e:
        print(f"Error processing webhook: Missing key {e}")
        return {"status": "error", "message": f"Missing required field: {e}"}

@app.get("/issues")
async def get_all_issues():
    """Get all issues with their state histories"""
    issues = db.get_all_issues()
    return {
        "status": "success",
        "count": len(issues),
        "issues": issues
    }

@app.get("/issues/{identifier}")
async def get_issue_history(identifier: str):
    """Get state history for a specific issue"""
    issue = db.get_issue_history(identifier)
    if issue:
        return {
            "status": "success",
            "issue": issue
        }
    else:
        raise HTTPException(status_code=404, detail=f"Issue {identifier} not found")

@app.get("/issues/state/{state}")
async def get_issues_by_state(state: str):
    """Get all issues currently in a specific state"""
    issues = db.get_issues_by_state(state)
    return {
        "status": "success",
        "state": state,
        "count": len(issues),
        "issues": issues
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Linear Issue Tracker"}

# API Key Configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable is required")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key for protected endpoints"""
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Please provide X-API-Key header."
        )
    return x_api_key

def calculate_state_transition_metrics(issues, state_positions):
    """Calculate average time between state transitions"""
    from datetime import datetime
    from collections import defaultdict
    
    transition_times = defaultdict(list)
    
    for issue in issues:
        state_history = issue['state_history']
        # Only look at states in our target states
        filtered_history = {state: time for state, time in state_history.items() 
                          if state in state_positions}
        
        if len(filtered_history) < 2:
            continue
            
        # Sort by timestamp
        sorted_states = sorted(filtered_history.items(), key=lambda x: x[1])
        
        # Calculate time between consecutive states
        for i in range(len(sorted_states) - 1):
            from_state = sorted_states[i][0]
            to_state = sorted_states[i + 1][0]
            
            from_time = datetime.fromisoformat(sorted_states[i][1].replace('Z', '+00:00'))
            to_time = datetime.fromisoformat(sorted_states[i + 1][1].replace('Z', '+00:00'))
            
            duration = (to_time - from_time).total_seconds() / 3600  # Convert to hours
            transition_times[f"{from_state} → {to_state}"].append(duration)
    
    # Calculate averages
    avg_transitions = {}
    for transition, times in transition_times.items():
        if times:
            avg_transitions[transition] = {
                "avg_hours": round(sum(times) / len(times), 2),
                "count": len(times),
                "min_hours": round(min(times), 2),
                "max_hours": round(max(times), 2)
            }
    
    return avg_transitions

@app.get("/visualize/timeline", dependencies=[Depends(verify_api_key)])
async def get_timeline_visualization(
    format: Optional[str] = "html",
    filter_states: Optional[str] = None
):
    """
    Generate timeline visualization
    
    Parameters:
    - format: "html" for interactive or "png" for static image
    - filter_states: Comma-separated list of states to filter (e.g., "In Master,Agent Running")
    
    Requires X-API-Key header with valid API key
    """
    # Parse filter states
    filter_state_set = None
    if filter_states:
        filter_state_set = set(s.strip() for s in filter_states.split(','))
    
    # Get all issues from database
    issues = db.get_all_issues()
    
    if not issues:
        raise HTTPException(status_code=404, detail="No issues found in database")
    
    if format == "html":
        # Generate interactive HTML visualization
        import plotly.graph_objects as go
        import plotly.express as px
        from datetime import datetime
        
        # State positions for Y-axis (only target states)
        STATE_POSITIONS = {
            "Agent Running": 0,
            "Agent Change Needs Review": 1,
            "In Master": 2
        }
        
        # Always filter for only target states
        target_states = set(STATE_POSITIONS.keys())
        filtered_issues = []
        for issue in issues:
            # Check if issue has been in any of the target states
            if set(issue['state_history'].keys()).intersection(target_states):
                filtered_issues.append(issue)
        
        # Apply additional filter if requested
        if filter_state_set:
            further_filtered = []
            for issue in filtered_issues:
                if set(issue['state_history'].keys()).intersection(filter_state_set):
                    further_filtered.append(issue)
            filtered_issues = further_filtered
        
        issues = filtered_issues
        
        if not issues:
            raise HTTPException(status_code=404, detail="No issues found with specified states")
        
        # Create Plotly figure
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly + px.colors.qualitative.D3
        
        for i, issue in enumerate(issues):
            color = colors[i % len(colors)]
            state_history = issue['state_history']
            
            if not state_history:
                continue
                
            sorted_states = sorted(state_history.items(), key=lambda x: x[1])
            
            times = []
            positions = []
            hover_texts = []
            
            for state, timestamp in sorted_states:
                # Only include states that are in our target states
                if state in STATE_POSITIONS:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    times.append(dt)
                    y_pos = STATE_POSITIONS[state]
                    positions.append(y_pos)
                    
                    hover_text = f"Issue: {issue['identifier']}<br>"
                    hover_text += f"Title: {issue['title']}<br>"
                    hover_text += f"State: {state}<br>"
                    hover_text += f"Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                    hover_texts.append(hover_text)
            
            # Add trace only if we have data points
            if times and positions:
                fig.add_trace(go.Scatter(
                    x=times,
                    y=positions,
                    mode='lines+markers+text',
                    name=issue['identifier'],
                    line=dict(color=color, width=2),
                    marker=dict(size=10),
                    text=[issue['identifier'] if i == len(times)-1 else '' for i in range(len(times))],
                    textposition='top right',
                    hovertext=hover_texts,
                    hoverinfo='text'
                ))
        
        # Calculate transition metrics
        transition_metrics = calculate_state_transition_metrics(issues, STATE_POSITIONS)
        
        # Update layout
        title = 'Linear Issue State Transitions Timeline'
        if filter_state_set:
            title += f'<br><sub>Filtered: {", ".join(filter_state_set)}</sub>'
        
        # Add metrics to title
        if transition_metrics:
            title += '<br><sub style="font-size: 12px; margin-top: 10px;">Average Time Between States:</sub>'
            for transition, metrics in sorted(transition_metrics.items()):
                title += f'<br><sub style="font-size: 11px;">{transition}: {metrics["avg_hours"]}h (min: {metrics["min_hours"]}h, max: {metrics["max_hours"]}h, count: {metrics["count"]})</sub>'
            
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(title='Date', showgrid=True),
            yaxis=dict(
                title='State',
                tickmode='array',
                tickvals=list(STATE_POSITIONS.values()),
                ticktext=list(STATE_POSITIONS.keys()),
                showgrid=True,
                range=[-0.5, max(STATE_POSITIONS.values()) + 0.5]
            ),
            height=700,  # Increased height to accommodate metrics
            width=1200,
            hovermode='closest',
            margin=dict(t=150)  # More top margin for metrics
        )
        
        # Create HTML with metrics table
        metrics_html = ""
        if transition_metrics:
            metrics_html = """
            <div style="margin: 20px; font-family: Arial, sans-serif;">
                <h3>State Transition Metrics</h3>
                <table style="border-collapse: collapse; width: 100%; max-width: 800px;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Transition</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Avg Time</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Min Time</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Max Time</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Count</th>
                    </tr>
            """
            for transition, metrics in sorted(transition_metrics.items()):
                metrics_html += f"""
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;">{transition}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{metrics['avg_hours']}h</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{metrics['min_hours']}h</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{metrics['max_hours']}h</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{metrics['count']}</td>
                    </tr>
                """
            metrics_html += "</table></div>"
        
        # Return HTML with metrics
        html_content = fig.to_html(include_plotlyjs='cdn')
        html_content = html_content.replace('</body>', metrics_html + '</body>')
        return HTMLResponse(content=html_content)
        
    elif format == "png":
        # Generate static PNG image
        import matplotlib
        matplotlib.use('Agg')  # Use non-GUI backend
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        
        # State positions (only target states)
        STATE_POSITIONS = {
            "Agent Running": 0,
            "Agent Change Needs Review": 1,
            "In Master": 2
        }
        
        # Always filter for only target states
        target_states = set(STATE_POSITIONS.keys())
        filtered_issues = []
        for issue in issues:
            # Check if issue has been in any of the target states
            if set(issue['state_history'].keys()).intersection(target_states):
                filtered_issues.append(issue)
        
        # Apply additional filter if requested
        if filter_state_set:
            further_filtered = []
            for issue in filtered_issues:
                if set(issue['state_history'].keys()).intersection(filter_state_set):
                    further_filtered.append(issue)
            filtered_issues = further_filtered
        
        issues = filtered_issues
        
        if not issues:
            raise HTTPException(status_code=404, detail="No issues found with specified states")
        
        # Create plot with better styling
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Use a better color palette
        import matplotlib.cm as cm
        import numpy as np
        
        # Create a color map with distinct colors
        n_issues = min(len(issues), 25)  # Increase limit for visibility
        colors = cm.rainbow(np.linspace(0, 1, n_issues))
        
        # Track positions for jitter calculation
        position_tracker = {}  # {(state, approx_time): count}
        
        # First pass: collect all points to calculate overlaps
        all_points = []
        for issue in issues[:n_issues]:
            state_history = issue['state_history']
            if not state_history:
                continue
                
            sorted_states = sorted(state_history.items(), key=lambda x: x[1])
            for state, timestamp in sorted_states:
                if state in STATE_POSITIONS:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    all_points.append((dt, STATE_POSITIONS[state], issue['identifier']))
        
        # Calculate jitter offsets
        jitter_offsets = {}
        jitter_amount = 0.15  # Vertical jitter amount
        
        for dt, y_pos, identifier in all_points:
            # Round time to nearest hour for grouping
            time_key = dt.replace(minute=0, second=0, microsecond=0)
            pos_key = (y_pos, time_key)
            
            if pos_key not in position_tracker:
                position_tracker[pos_key] = []
            position_tracker[pos_key].append(identifier)
        
        # Assign jitter offsets for overlapping points
        for pos_key, identifiers in position_tracker.items():
            if len(identifiers) > 1:
                # Distribute points vertically
                n_overlaps = len(identifiers)
                offsets = np.linspace(-jitter_amount, jitter_amount, n_overlaps)
                for idx, identifier in enumerate(identifiers):
                    if identifier not in jitter_offsets:
                        jitter_offsets[identifier] = {}
                    jitter_offsets[identifier][pos_key] = offsets[idx]
        
        # Second pass: plot with jitter
        for i, issue in enumerate(issues[:n_issues]):
            color = colors[i]
            state_history = issue['state_history']
            
            if not state_history:
                continue
                
            sorted_states = sorted(state_history.items(), key=lambda x: x[1])
            
            times = []
            positions = []
            
            for state, timestamp in sorted_states:
                # Only include states that are in our target states
                if state in STATE_POSITIONS:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    times.append(dt)
                    y_pos = STATE_POSITIONS[state]
                    
                    # Apply jitter if needed
                    time_key = dt.replace(minute=0, second=0, microsecond=0)
                    pos_key = (y_pos, time_key)
                    
                    if issue['identifier'] in jitter_offsets and pos_key in jitter_offsets[issue['identifier']]:
                        y_pos += jitter_offsets[issue['identifier']][pos_key]
                    
                    positions.append(y_pos)
            
            # Plot line only if we have data points
            if times and positions:
                # Plot the line with a subtle style
                ax.plot(times, positions, '-', 
                       color=color, linewidth=2.5, alpha=0.6,
                       label=issue['identifier'])
                
                # Plot points with different markers based on position
                for t, p in zip(times, positions):
                    state_idx = round(p)  # Get original state index
                    if state_idx == 0:  # Agent Running
                        marker = 'o'
                    elif state_idx == 1:  # Agent Change Needs Review
                        marker = 's'  # Square
                    else:  # In Master
                        marker = '^'  # Triangle
                    
                    ax.plot(t, p, marker, color=color, markersize=10,
                           markeredgecolor='black', markeredgewidth=1)
                
                # Add label at end with background
                ax.text(times[-1], positions[-1], 
                       f" {issue['identifier']}", 
                       fontsize=10, color=color,
                       verticalalignment='center',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                                edgecolor=color, alpha=0.8))
        
        # Configure plot with enhanced styling
        ax.set_yticks(list(STATE_POSITIONS.values()))
        ax.set_yticklabels(list(STATE_POSITIONS.keys()), fontsize=12)
        ax.set_ylabel('Issue State', fontsize=14, weight='bold')
        ax.set_xlabel('Date', fontsize=14, weight='bold')
        
        # Add horizontal lines for each state level
        for state, pos in STATE_POSITIONS.items():
            ax.axhline(y=pos, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
        
        # Format dates with better readability
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        fig.autofmt_xdate(rotation=45)
        
        # Add vertical grid for dates
        ax.grid(True, axis='x', alpha=0.2, linestyle=':')
        
        # Add padding to y-axis
        ax.set_ylim(-0.7, max(STATE_POSITIONS.values()) + 0.7)
        
        # Calculate transition metrics
        transition_metrics = calculate_state_transition_metrics(issues, STATE_POSITIONS)
        
        title = 'Linear Issue State Transitions'
        subtitle = 'Target States: In Master, Agent Change Needs Review, Agent Running'
        if filter_state_set:
            subtitle += f'\nFiltered: {", ".join(filter_state_set)}'
        
        # Add main title
        ax.set_title(title, fontsize=16, weight='bold', pad=20)
        # Add subtitle
        ax.text(0.5, 1.02, subtitle, transform=ax.transAxes, 
                fontsize=11, ha='center', va='bottom', color='gray')
        
        # Add metrics text
        if transition_metrics:
            metrics_text = "Average Time Between States:\n"
            for transition, metrics in sorted(transition_metrics.items()):
                metrics_text += f"{transition}: {metrics['avg_hours']}h (n={metrics['count']})\n"
            
            # Add text box with metrics
            ax.text(0.02, 0.98, metrics_text.strip(),
                   transform=ax.transAxes,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.8),
                   fontsize=10,
                   family='monospace')
        
        # Add legend with better positioning
        if len(issues) <= 15:
            # Issue legend
            leg1 = ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', 
                           title='Issues', fontsize=9, title_fontsize=10,
                           framealpha=0.9)
            
            # Add marker legend
            from matplotlib.lines import Line2D
            marker_elements = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', 
                      markeredgecolor='black', markersize=10, label='Agent Running'),
                Line2D([0], [0], marker='s', color='w', markerfacecolor='gray', 
                      markeredgecolor='black', markersize=10, label='Agent Change Needs Review'),
                Line2D([0], [0], marker='^', color='w', markerfacecolor='gray', 
                      markeredgecolor='black', markersize=10, label='In Master')
            ]
            ax.legend(handles=marker_elements, bbox_to_anchor=(1.02, 0.5), 
                     loc='center left', title='State Markers', fontsize=9,
                     title_fontsize=10, framealpha=0.9)
            
            # Add back the first legend
            ax.add_artist(leg1)
        
        plt.tight_layout()
        
        # Generate unique filename with timestamp
        timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"linear_timeline_{timestamp}_{unique_id}.png"
        file_path = os.path.join("/Users/udaysidagana/Desktop/Jakarta/LinearStatusVisualization./generated_images", filename)
        
        # Save to file
        plt.savefig(file_path, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # Upload to Google Drive and get shareable link
        upload_result = upload_to_google_drive_and_get_link(file_path, filename)
        
        # Clean up the local file (optional - you might want to keep it for caching)
        try:
            os.remove(file_path)
        except:
            pass  # Don't fail if cleanup fails
        
        if upload_result['success']:
            return JSONResponse(content={
                "status": "success",
                "shareable_link": upload_result['shareable_link'],
                "file_id": upload_result['file_id'],
                "filename": upload_result['filename'],
                "message": "Visualization generated and uploaded successfully"
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload visualization: {upload_result['error']}"
            )
    
    else:
        raise HTTPException(status_code=400, detail="Format must be 'html' or 'png'")

@app.get("/visualize/stats", dependencies=[Depends(verify_api_key)])
async def get_visualization_stats(format: Optional[str] = "json"):
    """
    Get statistics about issues for visualization
    
    Requires X-API-Key header with valid API key
    """
    issues = db.get_all_issues()
    
    # Target states for metrics
    TARGET_STATES = {
        "Agent Running": 0,
        "Agent Change Needs Review": 1,
        "In Master": 2
    }
    
    # Calculate statistics
    state_counts = {}
    state_transitions = {}
    issues_per_team = {}
    
    for issue in issues:
        # Current state distribution
        current_state = issue['current_state']
        state_counts[current_state] = state_counts.get(current_state, 0) + 1
        
        # Team distribution
        team = issue.get('team_name', 'Unknown')
        issues_per_team[team] = issues_per_team.get(team, 0) + 1
        
        # Count transitions
        states = sorted(issue['state_history'].items(), key=lambda x: x[1])
        for i in range(len(states) - 1):
            transition = f"{states[i][0]} → {states[i+1][0]}"
            state_transitions[transition] = state_transitions.get(transition, 0) + 1
    
    # Calculate transition metrics for target states
    transition_metrics = calculate_state_transition_metrics(issues, TARGET_STATES)
    
    stats_data = {
        "total_issues": len(issues),
        "state_distribution": state_counts,
        "team_distribution": issues_per_team,
        "common_transitions": dict(sorted(state_transitions.items(), 
                                         key=lambda x: x[1], 
                                         reverse=True)[:10]),
        "states_tracked": list(set(state for issue in issues 
                                  for state in issue['state_history'].keys())),
        "target_state_metrics": transition_metrics
    }
    
    if format == "json":
        return stats_data
    elif format == "png":
        # Generate visual statistics chart
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        
        # 1. State Distribution Pie Chart
        ax1 = plt.subplot(2, 2, 1)
        if state_counts:
            colors = plt.cm.Set3(range(len(state_counts)))
            wedges, texts, autotexts = ax1.pie(state_counts.values(), labels=state_counts.keys(), 
                                               autopct='%1.1f%%', colors=colors)
            ax1.set_title('Current State Distribution', fontsize=14, weight='bold')
        
        # 2. Team Distribution Bar Chart
        ax2 = plt.subplot(2, 2, 2)
        if issues_per_team:
            teams = list(issues_per_team.keys())
            counts = list(issues_per_team.values())
            bars = ax2.bar(teams, counts, color='skyblue')
            ax2.set_title('Issues per Team', fontsize=14, weight='bold')
            ax2.set_xlabel('Team')
            ax2.set_ylabel('Number of Issues')
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add value labels on bars
            for bar, count in zip(bars, counts):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{count}', ha='center', va='bottom')
        
        # 3. Common Transitions
        ax3 = plt.subplot(2, 2, 3)
        if stats_data['common_transitions']:
            transitions = list(stats_data['common_transitions'].keys())[:10]
            trans_counts = list(stats_data['common_transitions'].values())[:10]
            
            y_pos = range(len(transitions))
            bars = ax3.barh(y_pos, trans_counts, color='lightgreen')
            ax3.set_yticks(y_pos)
            ax3.set_yticklabels(transitions, fontsize=10)
            ax3.set_xlabel('Count')
            ax3.set_title('Top 10 State Transitions', fontsize=14, weight='bold')
            
            # Add value labels
            for bar, count in zip(bars, trans_counts):
                width = bar.get_width()
                ax3.text(width, bar.get_y() + bar.get_height()/2.,
                        f' {count}', ha='left', va='center')
        
        # 4. Transition Metrics Summary
        ax4 = plt.subplot(2, 2, 4)
        ax4.axis('off')
        
        # Create metrics text
        metrics_text = f"Total Issues: {stats_data['total_issues']}\n\n"
        metrics_text += "Average Time Between States:\n"
        metrics_text += "-" * 40 + "\n"
        
        if transition_metrics:
            for transition, metrics in sorted(transition_metrics.items()):
                metrics_text += f"{transition}:\n"
                metrics_text += f"  Avg: {metrics['avg_hours']}h | "
                metrics_text += f"Min: {metrics['min_hours']}h | "
                metrics_text += f"Max: {metrics['max_hours']}h\n"
                metrics_text += f"  Count: {metrics['count']}\n\n"
        else:
            metrics_text += "No transition metrics available"
        
        ax4.text(0.1, 0.9, metrics_text, transform=ax4.transAxes,
                fontsize=11, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))
        ax4.set_title('Transition Metrics', fontsize=14, weight='bold', y=0.98)
        
        # Overall title
        fig.suptitle('Linear Issue Statistics Dashboard', fontsize=18, weight='bold')
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Generate unique filename
        timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"linear_stats_{timestamp}_{unique_id}.png"
        file_path = os.path.join("/Users/udaysidagana/Desktop/Jakarta/LinearStatusVisualization./generated_images", filename)
        
        # Save to file
        plt.savefig(file_path, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # Upload to Google Drive
        upload_result = upload_to_google_drive_and_get_link(file_path, filename)
        
        # Clean up local file
        try:
            os.remove(file_path)
        except:
            pass
        
        if upload_result['success']:
            return JSONResponse(content={
                "status": "success",
                "shareable_link": upload_result['shareable_link'],
                "file_id": upload_result['file_id'],
                "filename": upload_result['filename'],
                "message": "Statistics visualization generated and uploaded successfully",
                "stats_data": stats_data  # Include the raw data as well
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload statistics visualization: {upload_result['error']}"
            )
    else:
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'png'")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)