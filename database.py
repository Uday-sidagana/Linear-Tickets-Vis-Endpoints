import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List
import os

class IssueDatabase:
    def __init__(self, db_path: str = "linear_issues.db"):
        """Initialize the database connection and create tables if needed."""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create the issues table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create issues table with state history stored as JSON
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issues (
                    id TEXT PRIMARY KEY,
                    identifier TEXT UNIQUE NOT NULL,
                    team_id TEXT NOT NULL,
                    team_name TEXT,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    state_history TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            ''')
            
            # Create index for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_identifier 
                ON issues(identifier)
            ''')
            
            conn.commit()
    
    def create_issue(self, issue_data: Dict) -> bool:
        """Create a new issue record with initial state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract relevant data from webhook payload
                issue_id = issue_data['id']
                identifier = issue_data['identifier']
                team_id = issue_data['teamId']
                team_name = issue_data['team']['name']
                title = issue_data['title']
                created_at = issue_data['createdAt']
                state_name = issue_data['state']['name']
                
                # Initialize state history with the first state
                state_history = {
                    state_name: created_at
                }
                
                cursor.execute('''
                    INSERT INTO issues (
                        id, identifier, team_id, team_name, title,
                        created_at, state_history, current_state, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    issue_id, identifier, team_id, team_name, title,
                    created_at, json.dumps(state_history), state_name, created_at
                ))
                
                conn.commit()
                print(f"Created issue {identifier} with initial state: {state_name}")
                return True
                
        except sqlite3.IntegrityError:
            print(f"Issue {issue_data['identifier']} already exists")
            return False
        except Exception as e:
            print(f"Error creating issue: {e}")
            return False
    
    def update_issue_state(self, issue_data: Dict) -> bool:
        """Update issue state if it has changed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                identifier = issue_data['identifier']
                new_state = issue_data['state']['name']
                updated_at = issue_data['updatedAt']
                
                # Get current issue data
                cursor.execute('''
                    SELECT state_history, current_state 
                    FROM issues 
                    WHERE identifier = ?
                ''', (identifier,))
                
                result = cursor.fetchone()
                
                if not result:
                    print(f"Issue {identifier} not found, creating new record")
                    return self.create_issue(issue_data)
                
                state_history_json, current_state = result
                state_history = json.loads(state_history_json)
                
                # Check if state has changed
                if current_state != new_state:
                    # Add new state to history
                    state_history[new_state] = updated_at
                    
                    # Update the record
                    cursor.execute('''
                        UPDATE issues 
                        SET state_history = ?, 
                            current_state = ?, 
                            last_updated = ?,
                            title = ?
                        WHERE identifier = ?
                    ''', (
                        json.dumps(state_history), 
                        new_state, 
                        updated_at,
                        issue_data['title'],
                        identifier
                    ))
                    
                    conn.commit()
                    print(f"Updated issue {identifier}: {current_state} -> {new_state}")
                    return True
                else:
                    print(f"Issue {identifier} state unchanged: {current_state}")
                    return False
                    
        except Exception as e:
            print(f"Error updating issue state: {e}")
            return False
    
    def get_issue_history(self, identifier: str) -> Optional[Dict]:
        """Get the complete state history for an issue."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM issues WHERE identifier = ?
                ''', (identifier,))
                
                row = cursor.fetchone()
                
                if row:
                    columns = [description[0] for description in cursor.description]
                    issue_dict = dict(zip(columns, row))
                    issue_dict['state_history'] = json.loads(issue_dict['state_history'])
                    return issue_dict
                
                return None
                
        except Exception as e:
            print(f"Error getting issue history: {e}")
            return None
    
    def get_all_issues(self) -> List[Dict]:
        """Get all issues with their state histories."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM issues ORDER BY last_updated DESC')
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                issues = []
                for row in rows:
                    issue_dict = dict(zip(columns, row))
                    issue_dict['state_history'] = json.loads(issue_dict['state_history'])
                    issues.append(issue_dict)
                
                return issues
                
        except Exception as e:
            print(f"Error getting all issues: {e}")
            return []
    
    def get_issues_by_state(self, state: str) -> List[Dict]:
        """Get all issues currently in a specific state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM issues 
                    WHERE current_state = ? 
                    ORDER BY last_updated DESC
                ''', (state,))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                issues = []
                for row in rows:
                    issue_dict = dict(zip(columns, row))
                    issue_dict['state_history'] = json.loads(issue_dict['state_history'])
                    issues.append(issue_dict)
                
                return issues
                
        except Exception as e:
            print(f"Error getting issues by state: {e}")
            return []

