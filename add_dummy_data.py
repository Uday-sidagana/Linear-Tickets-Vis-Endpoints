#!/usr/bin/env python3
"""
Add dummy data to demonstrate timeline visualization
"""
from database import IssueDatabase
from datetime import datetime, timedelta
import random

# Initialize database
db = IssueDatabase()

# Define dummy issues with clear state progression
dummy_issues = [
    {
        "identifier": "DEMO-001",
        "title": "Demo Issue: Fast Track",
        "states": [
            ("Agent Running", datetime.now() - timedelta(days=7, hours=12)),
            ("Agent Change Needs Review", datetime.now() - timedelta(days=6, hours=8)),
            ("In Master", datetime.now() - timedelta(days=5))
        ]
    },
    {
        "identifier": "DEMO-002", 
        "title": "Demo Issue: Normal Flow",
        "states": [
            ("Agent Running", datetime.now() - timedelta(days=10)),
            ("Agent Change Needs Review", datetime.now() - timedelta(days=8, hours=4)),
            ("Agent Running", datetime.now() - timedelta(days=7, hours=16)),  # Back to running
            ("Agent Change Needs Review", datetime.now() - timedelta(days=6)),
            ("In Master", datetime.now() - timedelta(days=4, hours=12))
        ]
    },
    {
        "identifier": "DEMO-003",
        "title": "Demo Issue: Extended Review",
        "states": [
            ("Agent Running", datetime.now() - timedelta(days=14)),
            ("Agent Change Needs Review", datetime.now() - timedelta(days=12)),
            ("Agent Change Needs Review", datetime.now() - timedelta(days=10)),  # Stay in review
            ("Agent Change Needs Review", datetime.now() - timedelta(days=8)),
            ("In Master", datetime.now() - timedelta(days=3))
        ]
    }
]

# Add dummy issues to database
print("Adding dummy issues to database...")
print("=" * 60)

for issue_config in dummy_issues:
    print(f"\nAdding {issue_config['identifier']}: {issue_config['title']}")
    
    # Create initial issue with first state
    first_state = issue_config['states'][0]
    issue_data = {
        'id': f"dummy-{issue_config['identifier'].lower()}",
        'identifier': issue_config['identifier'],
        'title': issue_config['title'],
        'teamId': 'demo-team',
        'team': {
            'id': 'demo-team',
            'name': 'Demo Team'
        },
        'createdAt': first_state[1].isoformat() + 'Z',
        'updatedAt': first_state[1].isoformat() + 'Z',
        'state': {
            'id': f'state-{first_state[0].lower().replace(" ", "-")}',
            'name': first_state[0],
            'type': 'started' if first_state[0] == 'Agent Running' else 'unstarted'
        }
    }
    
    # Try to create the issue
    success = db.create_issue(issue_data)
    if success:
        print(f"  ✓ Created with initial state: {first_state[0]}")
    else:
        print(f"  - Issue already exists, updating states...")
    
    # Add subsequent state transitions
    for state_name, timestamp in issue_config['states'][1:]:
        issue_data['updatedAt'] = timestamp.isoformat() + 'Z'
        issue_data['state'] = {
            'id': f'state-{state_name.lower().replace(" ", "-")}',
            'name': state_name,
            'type': 'started' if state_name == 'Agent Running' else 'unstarted'
        }
        
        db.update_issue_state(issue_data)
        print(f"  ✓ Added state transition: {state_name} at {timestamp.strftime('%Y-%m-%d %H:%M')}")

print("\n" + "=" * 60)
print("Dummy data added successfully!")
print("\nSummary of demo issues:")
print("- DEMO-001: Fast track progression (7 days)")
print("- DEMO-002: Normal flow with back-and-forth (10 days)")
print("- DEMO-003: Extended review period (14 days)")
print("\nRun the visualization API to see these demo issues in the timeline.")
