from composio import Composio
import requests
import json
import os

# Initialize Composio and get access token
composio = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
connected_account_id = os.getenv("COMPOSIO_CONNECTED_ACCOUNT_ID")
if not connected_account_id:
    raise ValueError("COMPOSIO_CONNECTED_ACCOUNT_ID environment variable is required")
connected_account = composio.connected_accounts.get(connected_account_id)
access_token = connected_account.data['access_token']

print(f"Using access token: {access_token}")

# Linear GraphQL endpoint
url = 'https://api.linear.app/graphql'

# Headers with the access token
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

# GraphQL query and variables
data = {
    "query": """query TeamIssues($teamId: String!, $after: String) {
        team(id: $teamId) {
            id
            name
            issues(
                first: 50,
                after: $after,
                filter: {
                    state: {
                        name: {
                            in: ["In Master", "Agent Change Needs Review", "Agent Running"]
                        }
                    }
                }
            ) {
                nodes {
                    id
                    identifier
                    title
                    createdAt
                    updatedAt
                    state {
                        id
                        name
                        type
                    }
                    team {
                        id
                        name
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }""",
    "variables": {
        "teamId": os.getenv("LINEAR_TEAM_ID"),
        "after": None
    }
}

# Make the request
response = requests.post(url, headers=headers, json=data)

# Process and store the response
if response.status_code == 200:
    data = response.json()
    print(f"Response received successfully")
    
    # Import database module
    from database import IssueDatabase
    db = IssueDatabase()
    
    # Process issues
    issues = data['data']['team']['issues']['nodes']
    team_name = data['data']['team']['name']
    
    print(f"\nImporting {len(issues)} issues from team: {team_name}")
    print("="*60)
    
    for issue in issues:
        # Convert to webhook format for database
        issue_data = {
            'id': issue['id'],
            'identifier': issue['identifier'],
            'title': issue['title'],
            'teamId': issue['team']['id'],
            'team': {
                'id': issue['team']['id'],
                'name': issue['team']['name']
            },
            'createdAt': issue['createdAt'],
            'updatedAt': issue['updatedAt'],
            'state': {
                'id': issue['state']['id'],
                'name': issue['state']['name'],
                'type': issue['state']['type']
            }
        }
        
        # Try to create the issue
        success = db.create_issue(issue_data)
        if success:
            print(f"✓ Created: {issue_data['identifier']} - {issue_data['state']['name']}")
        else:
            # If it already exists, try to update if state changed
            existing = db.get_issue_history(issue_data['identifier'])
            if existing and existing['current_state'] != issue_data['state']['name']:
                db.update_issue_state(issue_data)
                print(f"✓ Updated: {issue_data['identifier']} - {existing['current_state']} → {issue_data['state']['name']}")
            else:
                print(f"- Skipped: {issue_data['identifier']} - already exists with same state")
    
    print("\n" + "="*60)
    print("Import complete!")
    
    # Show summary
    all_issues = db.get_all_issues()
    state_counts = {}
    for issue in all_issues:
        state = issue['current_state']
        state_counts[state] = state_counts.get(state, 0) + 1
    
    print(f"\nTotal issues in database: {len(all_issues)}")
    print("Issues by state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")
    
    print("\nNote: The visualization API only shows these states on the Y-axis:")
    print("  - Agent Running (Y=0)")
    print("  - Agent Change Needs Review (Y=1)")
    print("  - In Master (Y=2)")
else:
    print(f"Error: {response.status_code}")
    print(response.text)