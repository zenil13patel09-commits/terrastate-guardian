"""
Database models for TerraState Guardian
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
import json


class Database:
    """Database connection and operations"""
    
    def __init__(self, db_path: str = "terrastate.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Environments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS environments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # State snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                environment_id INTEGER NOT NULL,
                terraform_version TEXT,
                serial INTEGER,
                lineage TEXT,
                resource_count INTEGER DEFAULT 0,
                state_data TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (environment_id) REFERENCES environments(id)
            )
        """)
        
        # Baselines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                environment_id INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (environment_id) REFERENCES environments(id),
                FOREIGN KEY (snapshot_id) REFERENCES state_snapshots(id),
                UNIQUE(project_id, environment_id)
            )
        """)
        
        # Drift events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drift_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                baseline_id INTEGER NOT NULL,
                drift_type TEXT NOT NULL,
                resource_type TEXT,
                resource_name TEXT,
                details TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (snapshot_id) REFERENCES state_snapshots(id),
                FOREIGN KEY (baseline_id) REFERENCES baselines(id)
            )
        """)
        
        # Resources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                resource_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                provider TEXT,
                module TEXT,
                attributes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (snapshot_id) REFERENCES state_snapshots(id)
            )
        """)
        
        conn.commit()
        conn.close()


class User:
    """User model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, username: str, password: str) -> int:
        """Create a new user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user"""
        user = self.get_by_username(username)
        if user and user['password'] == password:
            return True
        return False


class Project:
    """Project model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, name: str, description: str = "") -> int:
        """Create a new project"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description)
        )
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return project_id
    
    def get_all(self) -> List[Dict]:
        """Get all projects"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_by_id(self, project_id: int) -> Optional[Dict]:
        """Get project by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get project by name"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


class Environment:
    """Environment model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, name: str, description: str = "") -> int:
        """Create a new environment"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO environments (name, description) VALUES (?, ?)",
            (name, description)
        )
        env_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return env_id
    
    def get_all(self) -> List[Dict]:
        """Get all environments"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM environments ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get environment by name"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM environments WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


class StateSnapshot:
    """State snapshot model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, project_id: int, environment_id: int, state_data: Dict,
               terraform_version: str = "", serial: int = 0, lineage: str = "") -> int:
        """Create a new state snapshot"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        state_json = json.dumps(state_data)
        resource_count = len(state_data.get('resources', []))
        
        cursor.execute("""
            INSERT INTO state_snapshots 
            (project_id, environment_id, terraform_version, serial, lineage, resource_count, state_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (project_id, environment_id, terraform_version, serial, lineage, resource_count, state_json))
        
        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return snapshot_id
    
    def get_by_id(self, snapshot_id: int) -> Optional[Dict]:
        """Get snapshot by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM state_snapshots WHERE id = ?", (snapshot_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            snapshot = dict(row)
            snapshot['state_data'] = json.loads(snapshot['state_data'])
            return snapshot
        return None
    
    def get_by_project(self, project_id: int, environment_id: Optional[int] = None) -> List[Dict]:
        """Get snapshots by project and optionally environment"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if environment_id:
            cursor.execute("""
                SELECT * FROM state_snapshots 
                WHERE project_id = ? AND environment_id = ?
                ORDER BY uploaded_at DESC
            """, (project_id, environment_id))
        else:
            cursor.execute("""
                SELECT * FROM state_snapshots 
                WHERE project_id = ?
                ORDER BY uploaded_at DESC
            """, (project_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        snapshots = []
        for row in rows:
            snapshot = dict(row)
            snapshot['state_data'] = json.loads(snapshot['state_data'])
            snapshots.append(snapshot)
        return snapshots
    
    def get_all(self) -> List[Dict]:
        """Get all snapshots"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, p.name as project_name, e.name as environment_name
            FROM state_snapshots s
            JOIN projects p ON s.project_id = p.id
            JOIN environments e ON s.environment_id = e.id
            ORDER BY s.uploaded_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class Baseline:
    """Baseline model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_or_update(self, project_id: int, environment_id: int, snapshot_id: int) -> int:
        """Create or update baseline for project-environment pair"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Check if baseline exists
        cursor.execute("""
            SELECT id FROM baselines 
            WHERE project_id = ? AND environment_id = ?
        """, (project_id, environment_id))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing baseline
            cursor.execute("""
                UPDATE baselines 
                SET snapshot_id = ?, created_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND environment_id = ?
            """, (snapshot_id, project_id, environment_id))
            baseline_id = existing['id']
        else:
            # Create new baseline
            cursor.execute("""
                INSERT INTO baselines (project_id, environment_id, snapshot_id)
                VALUES (?, ?, ?)
            """, (project_id, environment_id, snapshot_id))
            baseline_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return baseline_id
    
    def get_by_project_env(self, project_id: int, environment_id: int) -> Optional[Dict]:
        """Get baseline for project-environment pair"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM baselines 
            WHERE project_id = ? AND environment_id = ?
        """, (project_id, environment_id))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


class DriftEvent:
    """Drift event model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, snapshot_id: int, baseline_id: int, drift_type: str,
               resource_type: str = "", resource_name: str = "", details: str = "") -> int:
        """Create a drift event"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO drift_events 
            (snapshot_id, baseline_id, drift_type, resource_type, resource_name, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (snapshot_id, baseline_id, drift_type, resource_type, resource_name, details))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id
    
    def get_by_snapshot(self, snapshot_id: int) -> List[Dict]:
        """Get drift events for a snapshot"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM drift_events 
            WHERE snapshot_id = ?
            ORDER BY detected_at DESC
        """, (snapshot_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_all(self) -> List[Dict]:
        """Get all drift events"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, s.uploaded_at, p.name as project_name, e.name as environment_name
            FROM drift_events d
            JOIN state_snapshots s ON d.snapshot_id = s.id
            JOIN projects p ON s.project_id = p.id
            JOIN environments e ON s.environment_id = e.id
            ORDER BY d.detected_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class Resource:
    """Resource model"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, snapshot_id: int, resource_type: str, resource_name: str,
               provider: str = "", module: str = "", attributes: Dict = None) -> int:
        """Create a resource entry"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        attrs_json = json.dumps(attributes or {})
        
        cursor.execute("""
            INSERT INTO resources 
            (snapshot_id, resource_type, resource_name, provider, module, attributes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (snapshot_id, resource_type, resource_name, provider, module, attrs_json))
        
        resource_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return resource_id
    
    def get_by_snapshot(self, snapshot_id: int) -> List[Dict]:
        """Get resources for a snapshot"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM resources 
            WHERE snapshot_id = ?
            ORDER BY resource_type, resource_name
        """, (snapshot_id,))
        rows = cursor.fetchall()
        conn.close()
        
        resources = []
        for row in rows:
            resource = dict(row)
            resource['attributes'] = json.loads(resource['attributes'])
            resources.append(resource)
        return resources
    
    def get_all(self) -> List[Dict]:
        """Get all resources"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, s.uploaded_at, p.name as project_name, e.name as environment_name
            FROM resources r
            JOIN state_snapshots s ON r.snapshot_id = s.id
            JOIN projects p ON s.project_id = p.id
            JOIN environments e ON s.environment_id = e.id
            ORDER BY r.resource_type, r.resource_name
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_resource_counts_by_type(self, snapshot_id: int) -> Dict[str, int]:
        """Get resource counts grouped by type"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT resource_type, COUNT(*) as count
            FROM resources
            WHERE snapshot_id = ?
            GROUP BY resource_type
            ORDER BY count DESC
        """, (snapshot_id,))
        rows = cursor.fetchall()
        conn.close()
        return {row['resource_type']: row['count'] for row in rows}
