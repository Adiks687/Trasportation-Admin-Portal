import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Dict, List, Optional
import getpass
import sqlite3
import json

class DatabaseManager:
    def __init__(self, db_path='transportation_portal.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                department TEXT DEFAULT 'Transportation',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                failed_attempts INTEGER DEFAULT 0
            )
        ''')
        
        # Permissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_name TEXT UNIQUE NOT NULL,
                description TEXT,
                module TEXT NOT NULL
            )
        ''')
        
        # Role permissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                role TEXT NOT NULL,
                permission_id INTEGER NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (role, permission_id),
                FOREIGN KEY (permission_id) REFERENCES permissions (permission_id)
            )
        ''')
        
        # Access logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_logs (
                log_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                status TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP NULL,
                ip_address TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=(), fetch=False):
        """Execute SQL query and return results if needed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            if fetch:
                result = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                conn.commit()
                conn.close()
                return result, columns
            else:
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            conn.close()
            raise e
    
    def get_dataframe(self, query, params=()):
        """Get query results as pandas DataFrame"""
        result, columns = self.execute_query(query, params, fetch=True)
        if result and columns:
            return pd.DataFrame(result, columns=columns)
        return pd.DataFrame()

class TransportationPortalAccessManager:
    def __init__(self, db_path='transportation_portal.db'):
        self.db = DatabaseManager(db_path)
        self.current_user = None
        self.current_session = None
        
        # Initialize default data
        self._initialize_default_data()
    
    def _initialize_default_data(self):
        """Initialize default roles and permissions"""
        # Check if permissions already exist
        existing_perms = self.db.get_dataframe("SELECT COUNT(*) as count FROM permissions")
        if existing_perms.empty or existing_perms.iloc[0]['count'] == 0:
            self._create_default_permissions()
    
    def _create_default_permissions(self):
        """Create default permissions and roles"""
        default_permissions = [
            # Admin permissions
            ('admin_dashboard_view', 'View admin dashboard', 'admin'),
            ('user_management', 'Manage users and roles', 'admin'),
            ('system_config', 'Configure system settings', 'admin'),
            
            # Transportation management permissions
            ('fleet_view', 'View vehicle fleet', 'fleet'),
            ('fleet_manage', 'Manage vehicle fleet', 'fleet'),
            ('routes_view', 'View transportation routes', 'routes'),
            ('routes_manage', 'Manage transportation routes', 'routes'),
            ('schedules_view', 'View schedules', 'schedules'),
            ('schedules_manage', 'Manage schedules', 'schedules'),
            
            # Reporting permissions
            ('reports_view', 'View reports', 'reports'),
            ('reports_generate', 'Generate reports', 'reports'),
            ('analytics_view', 'View analytics', 'analytics'),
            
            # Client permissions
            ('client_dashboard_view', 'View client dashboard', 'client'),
            ('booking_manage', 'Manage bookings', 'client'),
            ('payment_view', 'View payments', 'client'),
        ]
        
        # Insert permissions
        for name, desc, module in default_permissions:
            self.db.execute_query('''
                INSERT OR IGNORE INTO permissions (permission_name, description, module)
                VALUES (?, ?, ?)
            ''', (name, desc, module))
        
        # Default role permissions mapping
        role_permissions = {
            'super_admin': list(range(1, len(default_permissions) + 1)),
            'fleet_manager': [4, 5, 6, 7, 10, 11],
            'schedule_manager': [8, 9, 10],
            'client_admin': [13, 14, 15],
            'viewer': [1, 4, 6, 8, 10, 13]
        }
        
        # Insert role permissions
        for role, permissions in role_permissions.items():
            for perm_id in permissions:
                self.db.execute_query('''
                    INSERT OR IGNORE INTO role_permissions (role, permission_id)
                    VALUES (?, ?)
                ''', (role, perm_id))
        
        # Create default admin user if not exists
        self.create_user("super_admin", "admin@transport.com", "admin123", "super_admin")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        return hashlib.sha256((password + salt).encode()).hexdigest() + ':' + salt
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            stored_hash, salt = hashed_password.split(':')
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == stored_hash
        except:
            return False
    
    def create_user(self, username: str, email: str, password: str, 
                   role: str, department: str = 'Transportation') -> str:
        """Create a new user account"""
        # Check if username or email already exists
        existing_user = self.db.get_dataframe(
            "SELECT username FROM users WHERE username = ? OR email = ?", 
            (username, email)
        )
        
        if not existing_user.empty:
            if username in existing_user['username'].values:
                return f"Error: Username '{username}' already exists"
            return f"Error: Email '{email}' already exists"
        
        user_id = f"USER_{self._get_next_user_id():06d}"
        password_hash = self._hash_password(password)
        
        self.db.execute_query('''
            INSERT INTO users (user_id, username, email, password_hash, role, department, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        ''', (user_id, username, email, password_hash, role, department))
        
        # Log the action
        self._log_access(user_id, 'USER_CREATE', f'user:{user_id}', 'SUCCESS')
        
        return f"User {username} created successfully with ID: {user_id}"
    
    def _get_next_user_id(self) -> int:
        """Get next available user ID number"""
        result = self.db.get_dataframe("SELECT COUNT(*) as count FROM users")
        return result.iloc[0]['count'] + 1 if not result.empty else 1
    
    def authenticate_user(self, username: str, password: str, ip_address: str = '') -> Dict:
        """Authenticate user and create session"""
        user_record = self.db.get_dataframe(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        
        if user_record.empty:
            return {'success': False, 'message': 'Invalid username or password'}
        
        user_data = user_record.iloc[0]
        
        # Check if account is active
        if user_data['status'] != 'active':
            return {'success': False, 'message': 'Account is not active'}
        
        # Check for too many failed attempts
        if user_data['failed_attempts'] >= 5:
            return {'success': False, 'message': 'Account locked due to too many failed attempts'}
        
        # Verify password
        if self._verify_password(password, user_data['password_hash']):
            # Reset failed attempts and update last login
            self.db.execute_query('''
                UPDATE users 
                SET failed_attempts = 0, last_login = CURRENT_TIMESTAMP 
                WHERE username = ?
            ''', (username,))
            
            # Create session
            session_id = self._create_session(user_data['user_id'], ip_address)
            
            # Log successful login
            self._log_access(user_data['user_id'], 'LOGIN', 'system', 'SUCCESS', ip_address)
            
            return {
                'success': True,
                'user_id': user_data['user_id'],
                'username': username,
                'role': user_data['role'],
                'session_id': session_id,
                'message': 'Login successful'
            }
        else:
            # Increment failed attempts
            current_attempts = user_data['failed_attempts'] + 1
            self.db.execute_query(
                "UPDATE users SET failed_attempts = ? WHERE username = ?",
                (current_attempts, username)
            )
            
            # Lock account if too many failures
            if current_attempts >= 5:
                self.db.execute_query(
                    "UPDATE users SET status = 'locked' WHERE username = ?",
                    (username,)
                )
            
            # Log failed attempt
            self._log_access(user_data['user_id'], 'LOGIN', 'system', 'FAILED', ip_address)
            
            return {'success': False, 'message': 'Invalid username or password'}
    
    def _create_session(self, user_id: str, ip_address: str) -> str:
        """Create a new user session"""
        session_id = secrets.token_urlsafe(32)
        
        self.db.execute_query('''
            INSERT INTO sessions (session_id, user_id, ip_address, is_active)
            VALUES (?, ?, ?, TRUE)
        ''', (session_id, user_id, ip_address))
        
        return session_id
    
    def logout_user(self, session_id: str) -> bool:
        """Logout user and end session"""
        result = self.db.execute_query('''
            UPDATE sessions 
            SET logout_time = CURRENT_TIMESTAMP, is_active = FALSE 
            WHERE session_id = ? AND is_active = TRUE
        ''', (session_id,))
        
        if result:
            # Get user_id for logging
            user_data = self.db.get_dataframe(
                "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
            )
            if not user_data.empty:
                self._log_access(user_data.iloc[0]['user_id'], 'LOGOUT', 'system', 'SUCCESS')
            return True
        return False
    
    def check_permission(self, user_id: str, permission_name: str) -> bool:
        """Check if user has specific permission"""
        user_record = self.db.get_dataframe(
            "SELECT role FROM users WHERE user_id = ?", (user_id,)
        )
        
        if user_record.empty:
            return False
        
        user_role = user_record.iloc[0]['role']
        
        # Check if role has this permission
        result = self.db.get_dataframe('''
            SELECT COUNT(*) as count 
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.permission_id
            WHERE rp.role = ? AND p.permission_name = ?
        ''', (user_role, permission_name))
        
        return not result.empty and result.iloc[0]['count'] > 0
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for a user"""
        permissions = self.db.get_dataframe('''
            SELECT p.permission_name
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.permission_id
            JOIN users u ON u.role = rp.role
            WHERE u.user_id = ?
            ORDER BY p.permission_name
        ''', (user_id,))
        
        return permissions['permission_name'].tolist() if not permissions.empty else []
    
    def _log_access(self, user_id: str, action: str, resource: str, 
                   status: str, ip_address: str = '') -> None:
        """Log user access attempts"""
        log_id = f"LOG_{self._get_next_log_id():08d}"
        
        self.db.execute_query('''
            INSERT INTO access_logs (log_id, user_id, action, resource, ip_address, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (log_id, user_id, action, resource, ip_address, status))
    
    def _get_next_log_id(self) -> int:
        """Get next available log ID number"""
        result = self.db.get_dataframe("SELECT COUNT(*) as count FROM access_logs")
        return result.iloc[0]['count'] + 1 if not result.empty else 1
    
    def update_user_role(self, admin_user_id: str, target_user_id: str, new_role: str) -> Dict:
        """Update user role (admin function)"""
        # Check if admin has permission
        if not self.check_permission(admin_user_id, 'user_management'):
            self._log_access(admin_user_id, 'ROLE_UPDATE', f'user:{target_user_id}', 'DENIED')
            return {'success': False, 'message': 'Insufficient permissions'}
        
        # Check if target user exists
        user_exists = self.db.get_dataframe(
            "SELECT COUNT(*) as count FROM users WHERE user_id = ?", (target_user_id,)
        )
        if user_exists.empty or user_exists.iloc[0]['count'] == 0:
            return {'success': False, 'message': 'User not found'}
        
        # Update role
        self.db.execute_query(
            "UPDATE users SET role = ? WHERE user_id = ?",
            (new_role, target_user_id)
        )
        
        # Log the action
        self._log_access(admin_user_id, 'ROLE_UPDATE', f'user:{target_user_id}', 'SUCCESS')
        
        return {'success': True, 'message': f'User role updated to {new_role}'}
    
    def get_active_users(self) -> pd.DataFrame:
        """Get currently active users"""
        return self.db.get_dataframe('''
            SELECT u.user_id, u.username, u.role, u.department, s.login_time, s.ip_address
            FROM sessions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.is_active = TRUE
            ORDER BY s.login_time DESC
        ''')
    
    def get_access_stats(self) -> Dict:
        """Get access statistics"""
        stats = {}
        
        # Total logs
        result = self.db.get_dataframe("SELECT COUNT(*) as count FROM access_logs")
        stats['total_logs'] = result.iloc[0]['count'] if not result.empty else 0
        
        # Successful logins
        result = self.db.get_dataframe('''
            SELECT COUNT(*) as count FROM access_logs 
            WHERE action = 'LOGIN' AND status = 'SUCCESS'
        ''')
        stats['successful_logins'] = result.iloc[0]['count'] if not result.empty else 0
        
        # Failed logins
        result = self.db.get_dataframe('''
            SELECT COUNT(*) as count FROM access_logs 
            WHERE action = 'LOGIN' AND status = 'FAILED'
        ''')
        stats['failed_logins'] = result.iloc[0]['count'] if not result.empty else 0
        
        # Unique users
        result = self.db.get_dataframe("SELECT COUNT(DISTINCT user_id) as count FROM access_logs")
        stats['unique_users'] = result.iloc[0]['count'] if not result.empty else 0
        
        # Recent activity (last 7 days)
        result = self.db.get_dataframe('''
            SELECT COUNT(*) as count FROM access_logs 
            WHERE timestamp >= datetime('now', '-7 days')
        ''')
        stats['recent_activity'] = result.iloc[0]['count'] if not result.empty else 0
        
        return stats
    
    def view_all_users(self) -> pd.DataFrame:
        """Get all users"""
        return self.db.get_dataframe('''
            SELECT user_id, username, email, role, department, status, created_at
            FROM users 
            ORDER BY created_at DESC
        ''')
    
    def view_user_details(self, username: str) -> Dict:
        """Get detailed user information"""
        user_data = self.db.get_dataframe(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        
        if user_data.empty:
            return {'error': 'User not found'}
        
        user_info = user_data.iloc[0].to_dict()
        user_info['permissions'] = self.get_user_permissions(user_info['user_id'])
        
        return user_info

# The main user interface remains the same as previous code
def main():
    """Main user interface for the Transportation Portal"""
    portal = TransportationPortalAccessManager()
    
    print("🚛 Welcome to Transportation Portal Access Management System 🚛")
    print("📊 Database: SQLite (transportation_portal.db)")
    
    while True:
        if portal.current_user is None:
            # Not logged in - show login menu
            print("\n" + "="*50)
            print("1. Login")
            print("2. Exit")
            print("="*50)
            
            choice = input("Enter your choice (1-2): ").strip()
            
            if choice == '1':
                print("\n--- Login ---")
                username = input("Username: ").strip()
                password = getpass.getpass("Password: ").strip()
                
                auth_result = portal.authenticate_user(username, password, "127.0.0.1")
                
                if auth_result['success']:
                    portal.current_user = auth_result
                    portal.current_session = auth_result['session_id']
                    print(f"\n✅ {auth_result['message']}")
                    print(f"Welcome, {auth_result['username']}!")
                    print(f"Role: {auth_result['role']}")
                else:
                    print(f"\n❌ {auth_result['message']}")
                    
            elif choice == '2':
                print("Thank you for using Transportation Portal. Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")
                
        else:
            # Logged in - show main menu
            user_role = portal.current_user['role']
            username = portal.current_user['username']
            user_id = portal.current_user['user_id']
            
            print(f"\n" + "="*50)
            print(f"Welcome, {username} ({user_role})")
            print("="*50)
            
            print("1. View My Permissions")
            print("2. View All Users")
            print("3. View User Details")
            print("4. View System Statistics")
            print("5. View Active Users")
            
            if portal.check_permission(user_id, 'user_management'):
                print("6. Create New User")
                print("7. Update User Role")
            
            if portal.check_permission(user_id, 'fleet_view'):
                print("8. View Fleet")
            if portal.check_permission(user_id, 'routes_view'):
                print("9. View Routes")
            if portal.check_permission(user_id, 'schedules_view'):
                print("10. View Schedules")
            
            print("99. Logout")
            print("0. Exit System")
            
            choice = input(f"\nEnter your choice: ").strip()
            
            if choice == '1':
                permissions = portal.get_user_permissions(user_id)
                print(f"\n=== YOUR PERMISSIONS ({len(permissions)}) ===")
                for perm in permissions:
                    print(f"✓ {perm}")
                    
            elif choice == '2':
                users_df = portal.view_all_users()
                if not users_df.empty:
                    print("\n=== ALL SYSTEM USERS ===")
                    print(users_df.to_string(index=False))
                else:
                    print("No users found.")
                    
            elif choice == '3':
                username = input("Enter username to view details: ").strip()
                user_details = portal.view_user_details(username)
                if 'error' in user_details:
                    print(f"Error: {user_details['error']}")
                else:
                    print(f"\n=== USER DETAILS: {username} ===")
                    for key, value in user_details.items():
                        if key != 'permissions' and key != 'password_hash':
                            print(f"{key}: {value}")
                    print(f"Permissions: {len(user_details['permissions'])}")
                    
            elif choice == '4':
                stats = portal.get_access_stats()
                print("\n=== SYSTEM STATISTICS ===")
                for key, value in stats.items():
                    print(f"{key.replace('_', ' ').title()}: {value}")
                    
            elif choice == '5':
                active_users = portal.get_active_users()
                if not active_users.empty:
                    print("\n=== ACTIVE USERS ===")
                    print(active_users.to_string(index=False))
                else:
                    print("\nNo active users.")
                    
            elif choice == '6' and portal.check_permission(user_id, 'user_management'):
                print("\n--- Create New User ---")
                new_username = input("Username: ").strip()
                new_email = input("Email: ").strip()
                new_password = getpass.getpass("Password: ").strip()
                new_role = input("Role (super_admin/fleet_manager/schedule_manager/client_admin/viewer): ").strip()
                new_department = input("Department: ").strip() or "Transportation"
                
                result = portal.create_user(new_username, new_email, new_password, new_role, new_department)
                print(f"\n{result}")
                
            elif choice == '7' and portal.check_permission(user_id, 'user_management'):
                print("\n--- Update User Role ---")
                users_df = portal.view_all_users()
                if not users_df.empty:
                    print(users_df[['user_id', 'username', 'role']].to_string(index=False))
                target_user = input("Enter user ID to update: ").strip()
                new_role = input("Enter new role: ").strip()
                
                result = portal.update_user_role(user_id, target_user, new_role)
                print(f"\n{result['message']}")
                
            elif choice == '8' and portal.check_permission(user_id, 'fleet_view'):
                print("\n=== VEHICLE FLEET ===")
                print("Fleet management interface would be here...")
                
            elif choice == '9' and portal.check_permission(user_id, 'routes_view'):
                print("\n=== TRANSPORTATION ROUTES ===")
                print("Routes management interface would be here...")
                
            elif choice == '10' and portal.check_permission(user_id, 'schedules_view'):
                print("\n=== TRANSPORTATION SCHEDULES ===")
                print("Schedules management interface would be here...")
                
            elif choice == '99':
                if portal.current_session:
                    portal.logout_user(portal.current_session)
                portal.current_user = None
                portal.current_session = None
                print("You have been logged out successfully.")
                
            elif choice == '0':
                if portal.current_session:
                    portal.logout_user(portal.current_session)
                print("Thank you for using Transportation Portal. Goodbye!")
                break
                
            else:
                print("Invalid choice or insufficient permissions. Please try again.")

if __name__ == "__main__":
    main()