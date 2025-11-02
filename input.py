import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Dict, List, Optional
import getpass  # For secure password input

class TransportationPortalAccessManager:
    def __init__(self):
        # Initialize data structures
        self.users_df = pd.DataFrame(columns=[
            'user_id', 'username', 'email', 'password_hash', 'role', 
            'department', 'status', 'created_at', 'last_login', 'failed_attempts'
        ])
        
        self.permissions_df = pd.DataFrame(columns=[
            'permission_id', 'permission_name', 'description', 'module'
        ])
        
        self.role_permissions_df = pd.DataFrame(columns=[
            'role', 'permission_id', 'granted_at'
        ])
        
        self.access_logs_df = pd.DataFrame(columns=[
            'log_id', 'user_id', 'action', 'resource', 'timestamp', 
            'ip_address', 'status'
        ])
        
        self.sessions_df = pd.DataFrame(columns=[
            'session_id', 'user_id', 'login_time', 'logout_time', 
            'ip_address', 'is_active'
        ])
        
        self.current_user = None
        self.current_session = None
        
        # Initialize default roles and permissions
        self._initialize_default_permissions()
    
    def _initialize_default_permissions(self):
        """Initialize default roles and permissions for the transportation portal"""
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
        
        for i, (name, desc, module) in enumerate(default_permissions, 1):
            self.permissions_df = pd.concat([self.permissions_df, pd.DataFrame([{
                'permission_id': i,
                'permission_name': name,
                'description': desc,
                'module': module
            }])], ignore_index=True)
        
        # Default role permissions
        role_permissions = {
            'super_admin': list(range(1, len(default_permissions) + 1)),
            'fleet_manager': [4, 5, 6, 7, 10, 11],  # fleet and routes management
            'schedule_manager': [8, 9, 10],  # schedules and basic reports
            'client_admin': [13, 14, 15],  # client management
            'viewer': [1, 4, 6, 8, 10, 13]  # view-only access
        }
        
        for role, permissions in role_permissions.items():
            for perm_id in permissions:
                self.role_permissions_df = pd.concat([self.role_permissions_df, pd.DataFrame([{
                    'role': role,
                    'permission_id': perm_id,
                    'granted_at': datetime.now()
                }])], ignore_index=True)
    
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
        if not self.users_df.empty:
            if username in self.users_df['username'].values:
                return f"Error: Username '{username}' already exists"
            if email in self.users_df['email'].values:
                return f"Error: Email '{email}' already exists"
        
        user_id = f"USER_{len(self.users_df) + 1:06d}"
        password_hash = self._hash_password(password)
        
        new_user = pd.DataFrame([{
            'user_id': user_id,
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'department': department,
            'status': 'active',
            'created_at': datetime.now(),
            'last_login': None,
            'failed_attempts': 0
        }])
        
        self.users_df = pd.concat([self.users_df, new_user], ignore_index=True)
        
        # Log the action
        self._log_access(user_id, 'USER_CREATE', f'user:{user_id}', 'SUCCESS')
        
        return f"User {username} created successfully with ID: {user_id}"
    
    def authenticate_user(self, username: str, password: str, ip_address: str = '') -> Dict:
        """Authenticate user and create session"""
        if self.users_df.empty:
            return {'success': False, 'message': 'No users registered'}
        
        user_record = self.users_df[self.users_df['username'] == username]
        
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
            # Reset failed attempts
            self.users_df.loc[self.users_df['username'] == username, 'failed_attempts'] = 0
            self.users_df.loc[self.users_df['username'] == username, 'last_login'] = datetime.now()
            
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
            self.users_df.loc[self.users_df['username'] == username, 'failed_attempts'] = current_attempts
            
            # Lock account if too many failures
            if current_attempts >= 5:
                self.users_df.loc[self.users_df['username'] == username, 'status'] = 'locked'
            
            # Log failed attempt
            self._log_access(user_data['user_id'], 'LOGIN', 'system', 'FAILED', ip_address)
            
            return {'success': False, 'message': 'Invalid username or password'}
    
    def _create_session(self, user_id: str, ip_address: str) -> str:
        """Create a new user session"""
        session_id = secrets.token_urlsafe(32)
        
        new_session = pd.DataFrame([{
            'session_id': session_id,
            'user_id': user_id,
            'login_time': datetime.now(),
            'logout_time': None,
            'ip_address': ip_address,
            'is_active': True
        }])
        
        self.sessions_df = pd.concat([self.sessions_df, new_session], ignore_index=True)
        return session_id
    
    def logout_user(self, session_id: str) -> bool:
        """Logout user and end session"""
        if session_id in self.sessions_df['session_id'].values:
            self.sessions_df.loc[self.sessions_df['session_id'] == session_id, 'logout_time'] = datetime.now()
            self.sessions_df.loc[self.sessions_df['session_id'] == session_id, 'is_active'] = False
            
            # Get user_id for logging
            user_id = self.sessions_df.loc[self.sessions_df['session_id'] == session_id, 'user_id'].iloc[0]
            self._log_access(user_id, 'LOGOUT', 'system', 'SUCCESS')
            
            return True
        return False
    
    def check_permission(self, user_id: str, permission_name: str) -> bool:
        """Check if user has specific permission"""
        if self.users_df.empty:
            return False
        
        user_record = self.users_df[self.users_df['user_id'] == user_id]
        if user_record.empty:
            return False
        
        user_role = user_record.iloc[0]['role']
        
        # Get permission ID
        perm_record = self.permissions_df[self.permissions_df['permission_name'] == permission_name]
        if perm_record.empty:
            return False
        
        permission_id = perm_record.iloc[0]['permission_id']
        
        # Check if role has this permission
        has_permission = not self.role_permissions_df[
            (self.role_permissions_df['role'] == user_role) & 
            (self.role_permissions_df['permission_id'] == permission_id)
        ].empty
        
        return has_permission
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for a user"""
        if self.users_df.empty:
            return []
        
        user_record = self.users_df[self.users_df['user_id'] == user_id]
        if user_record.empty:
            return []
        
        user_role = user_record.iloc[0]['role']
        
        # Get permission IDs for the role
        role_perms = self.role_permissions_df[self.role_permissions_df['role'] == user_role]
        if role_perms.empty:
            return []
        
        # Get permission names
        permission_ids = role_perms['permission_id'].tolist()
        permissions = self.permissions_df[self.permissions_df['permission_id'].isin(permission_ids)]
        
        return permissions['permission_name'].tolist()
    
    def _log_access(self, user_id: str, action: str, resource: str, 
                   status: str, ip_address: str = '') -> None:
        """Log user access attempts"""
        log_id = f"LOG_{len(self.access_logs_df) + 1:08d}"
        
        new_log = pd.DataFrame([{
            'log_id': log_id,
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'timestamp': datetime.now(),
            'ip_address': ip_address,
            'status': status
        }])
        
        self.access_logs_df = pd.concat([self.access_logs_df, new_log], ignore_index=True)
    
    def update_user_role(self, admin_user_id: str, target_user_id: str, new_role: str) -> Dict:
        """Update user role (admin function)"""
        # Check if admin has permission
        if not self.check_permission(admin_user_id, 'user_management'):
            self._log_access(admin_user_id, 'ROLE_UPDATE', f'user:{target_user_id}', 'DENIED')
            return {'success': False, 'message': 'Insufficient permissions'}
        
        if target_user_id not in self.users_df['user_id'].values:
            return {'success': False, 'message': 'User not found'}
        
        # Update role
        self.users_df.loc[self.users_df['user_id'] == target_user_id, 'role'] = new_role
        
        # Log the action
        self._log_access(admin_user_id, 'ROLE_UPDATE', f'user:{target_user_id}', 'SUCCESS')
        
        return {'success': True, 'message': f'User role updated to {new_role}'}
    
    def get_active_users(self) -> pd.DataFrame:
        """Get currently active users"""
        if self.sessions_df.empty:
            return pd.DataFrame()
        
        active_sessions = self.sessions_df[self.sessions_df['is_active'] == True]
        if active_sessions.empty:
            return pd.DataFrame()
        
        # Join with users dataframe
        active_users = pd.merge(
            active_sessions, 
            self.users_df, 
            on='user_id', 
            how='left'
        )[['user_id', 'username', 'role', 'department', 'login_time', 'ip_address']]
        
        return active_users
    
    def get_access_stats(self) -> Dict:
        """Get access statistics"""
        if self.access_logs_df.empty:
            return {}
        
        stats = {
            'total_logs': len(self.access_logs_df),
            'successful_logins': len(self.access_logs_df[
                (self.access_logs_df['action'] == 'LOGIN') & 
                (self.access_logs_df['status'] == 'SUCCESS')
            ]),
            'failed_logins': len(self.access_logs_df[
                (self.access_logs_df['action'] == 'LOGIN') & 
                (self.access_logs_df['status'] == 'FAILED')
            ]),
            'unique_users': self.access_logs_df['user_id'].nunique(),
        }
        
        # Recent activity (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_logs = self.access_logs_df[self.access_logs_df['timestamp'] > week_ago]
        stats['recent_activity'] = len(recent_logs)
        
        return stats
    
    def generate_user_report(self) -> pd.DataFrame:
        """Generate comprehensive user report"""
        if self.users_df.empty:
            return pd.DataFrame()
        
        report = self.users_df.copy()
        
        # Calculate days since creation
        report['days_since_creation'] = (datetime.now() - report['created_at']).dt.days
        
        # Get permission counts for each role
        role_permission_counts = self.role_permissions_df.groupby('role').size()
        report['permission_count'] = report['role'].map(role_permission_counts).fillna(0)
        
        # Get last activity
        if not self.access_logs_df.empty:
            last_activity = self.access_logs_df.groupby('user_id')['timestamp'].max()
            report['last_activity'] = report['user_id'].map(last_activity)
        
        return report

    def view_all_users(self) -> None:
        """Display all users in the system"""
        if self.users_df.empty:
            print("No users in the system.")
            return
        
        print("\n=== ALL SYSTEM USERS ===")
        display_df = self.users_df[['user_id', 'username', 'email', 'role', 'department', 'status']]
        print(display_df.to_string(index=False))

    def view_user_details(self, username: str) -> None:
        """Display detailed information about a specific user"""
        if self.users_df.empty:
            print("No users in the system.")
            return
        
        user_record = self.users_df[self.users_df['username'] == username]
        if user_record.empty:
            print(f"User '{username}' not found.")
            return
        
        user_data = user_record.iloc[0]
        print(f"\n=== USER DETAILS: {username} ===")
        print(f"User ID: {user_data['user_id']}")
        print(f"Username: {user_data['username']}")
        print(f"Email: {user_data['email']}")
        print(f"Role: {user_data['role']}")
        print(f"Department: {user_data['department']}")
        print(f"Status: {user_data['status']}")
        print(f"Created: {user_data['created_at']}")
        print(f"Last Login: {user_data['last_login']}")
        print(f"Failed Attempts: {user_data['failed_attempts']}")
        
        # Show permissions
        permissions = self.get_user_permissions(user_data['user_id'])
        print(f"\nPermissions ({len(permissions)}):")
        for perm in permissions:
            print(f"  - {perm}")

def main():
    """Main user interface for the Transportation Portal"""
    portal = TransportationPortalAccessManager()
    
    # Create some default users for testing
    portal.create_user("super_admin", "admin@transport.com", "admin123", "super_admin")
    portal.create_user("fleet_manager", "fleet@transport.com", "fleet123", "fleet_manager")
    portal.create_user("client_admin", "client@transport.com", "client123", "client_admin")
    
    print("🚛 Welcome to Transportation Portal Access Management System 🚛")
    
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
            # Logged in - show main menu based on user role
            user_role = portal.current_user['role']
            username = portal.current_user['username']
            user_id = portal.current_user['user_id']
            
            print(f"\n" + "="*50)
            print(f"Welcome, {username} ({user_role})")
            print("="*50)
            
            # Common menu options for all users
            print("1. View My Permissions")
            print("2. View All Users")
            print("3. View User Details")
            print("4. View System Statistics")
            print("5. View Active Users")
            
            # Admin-specific options
            if portal.check_permission(user_id, 'user_management'):
                print("6. Create New User")
                print("7. Update User Role")
            
            # Transportation management options
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
                # View My Permissions
                permissions = portal.get_user_permissions(user_id)
                print(f"\n=== YOUR PERMISSIONS ({len(permissions)}) ===")
                for perm in permissions:
                    print(f"✓ {perm}")
                    
            elif choice == '2':
                # View All Users
                portal.view_all_users()
                
            elif choice == '3':
                # View User Details
                username = input("Enter username to view details: ").strip()
                portal.view_user_details(username)
                
            elif choice == '4':
                # View System Statistics
                stats = portal.get_access_stats()
                print("\n=== SYSTEM STATISTICS ===")
                for key, value in stats.items():
                    print(f"{key.replace('_', ' ').title()}: {value}")
                    
            elif choice == '5':
                # View Active Users
                active_users = portal.get_active_users()
                if not active_users.empty:
                    print("\n=== ACTIVE USERS ===")
                    print(active_users.to_string(index=False))
                else:
                    print("\nNo active users.")
                    
            elif choice == '6' and portal.check_permission(user_id, 'user_management'):
                # Create New User
                print("\n--- Create New User ---")
                new_username = input("Username: ").strip()
                new_email = input("Email: ").strip()
                new_password = getpass.getpass("Password: ").strip()
                new_role = input("Role (super_admin/fleet_manager/schedule_manager/client_admin/viewer): ").strip()
                new_department = input("Department: ").strip() or "Transportation"
                
                result = portal.create_user(new_username, new_email, new_password, new_role, new_department)
                print(f"\n{result}")
                
            elif choice == '7' and portal.check_permission(user_id, 'user_management'):
                # Update User Role
                print("\n--- Update User Role ---")
                portal.view_all_users()
                target_user = input("Enter user ID to update: ").strip()
                new_role = input("Enter new role: ").strip()
                
                result = portal.update_user_role(user_id, target_user, new_role)
                print(f"\n{result['message']}")
                
            elif choice == '8' and portal.check_permission(user_id, 'fleet_view'):
                # View Fleet
                print("\n=== VEHICLE FLEET ===")
                print("This would display the vehicle fleet information...")
                # Add actual fleet viewing logic here
                
            elif choice == '9' and portal.check_permission(user_id, 'routes_view'):
                # View Routes
                print("\n=== TRANSPORTATION ROUTES ===")
                print("This would display the transportation routes...")
                # Add actual routes viewing logic here
                
            elif choice == '10' and portal.check_permission(user_id, 'schedules_view'):
                # View Schedules
                print("\n=== TRANSPORTATION SCHEDULES ===")
                print("This would display the transportation schedules...")
                # Add actual schedules viewing logic here
                
            elif choice == '99':
                # Logout
                if portal.current_session:
                    portal.logout_user(portal.current_session)
                portal.current_user = None
                portal.current_session = None
                print("You have been logged out successfully.")
                
            elif choice == '0':
                # Exit
                if portal.current_session:
                    portal.logout_user(portal.current_session)
                print("Thank you for using Transportation Portal. Goodbye!")
                break
                
            else:
                print("Invalid choice or insufficient permissions. Please try again.")

if __name__ == "__main__":
    main()
