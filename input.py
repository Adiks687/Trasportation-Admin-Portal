import pandas as pd
from datetime import datetime
import hashlib, secrets
from typing import Dict, List
import getpass  # for hidden password input

class TransportationPortalAccessManager:
    def __init__(self):
        # Core tables
        self.users_df = pd.DataFrame(columns=[
            'user_id','username','email','password_hash','role',
            'department','status','created_at','last_login','failed_attempts'
        ])
        self.permissions_df = pd.DataFrame(columns=[
            'permission_id','permission_name','description','module'
        ])
        self.role_permissions_df = pd.DataFrame(columns=[
            'role','permission_id','granted_at'
        ])
        self.access_logs_df = pd.DataFrame(columns=[
            'log_id','user_id','action','resource','timestamp','ip_address','status'
        ])
        self.sessions_df = pd.DataFrame(columns=[
            'session_id','user_id','login_time','logout_time','ip_address','is_active'
        ])
        self.trains_df = pd.DataFrame(columns=[
            'train_id','train_name','train_number','origin','destination',
            'departure_time','arrival_time','duration','seats_available','fare','train_type'
        ])

        # Runtime
        self.current_user = None
        self.current_session = None

        # Seed data
        self._initialize_default_permissions()
        self._initialize_train_schedules()
        self._create_default_users()

    # ---------- helpers ----------
    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        return hashlib.sha256((password + salt).encode()).hexdigest() + ':' + salt

    def _verify_password(self, password: str, hashed_password: str) -> bool:
        try:
            stored_hash, salt = hashed_password.split(':')
            return hashlib.sha256((password + salt).encode()).hexdigest() == stored_hash
        except Exception:
            return False

    def _log_access(self, user_id: str, action: str, resource: str, status: str, ip: str = ''):
        log_id = f"LOG_{len(self.access_logs_df) + 1:08d}"
        self.access_logs_df.loc[len(self.access_logs_df)] = {
            'log_id': log_id, 'user_id': user_id, 'action': action, 'resource': resource,
            'timestamp': datetime.now(), 'ip_address': ip, 'status': status
        }

    def _user_exists(self, username: str, email: str) -> bool:
        if self.users_df.empty:
            return False
        return (self.users_df['username'] == username).any() or (self.users_df['email'] == email).any()

    # ---------- seeders ----------
    def _initialize_default_permissions(self):
        perms = [
            ('admin_dashboard_view','View admin dashboard','admin'),
            ('user_management','Manage users and roles','admin'),
            ('system_config','Configure system settings','admin'),
            ('fleet_view','View vehicle fleet','fleet'),
            ('fleet_manage','Manage vehicle fleet','fleet'),
            ('routes_view','View transportation routes','routes'),
            ('routes_manage','Manage transportation routes','routes'),
            ('schedules_view','View schedules','schedules'),
            ('schedules_manage','Manage schedules','schedules'),
            ('reports_view','View reports','reports'),
            ('reports_generate','Generate reports','reports'),
            ('analytics_view','View analytics','analytics'),
            ('client_dashboard_view','View client dashboard','client'),
            ('booking_manage','Manage bookings','client'),
            ('payment_view','View payments','client'),
            ('train_booking','Book train tickets','booking'),
            ('train_view','View train schedules','booking'),
        ]
        self.permissions_df = pd.DataFrame(
            [{'permission_id': i+1, 'permission_name': n, 'description': d, 'module': m}
             for i, (n, d, m) in enumerate(perms)]
        )

        role_perms = {
            'super_admin': list(range(1, len(perms)+1)),
            'fleet_manager': [4,5,6,7,10,11],
            'schedule_manager': [8,9,10],
            'client_admin': [13,14,15],
            'viewer': [1,4,6,8,10,13,16,17],
            'passenger': [13,16,17]
        }
        now = datetime.now()
        self.role_permissions_df = pd.DataFrame(
            [{'role': r, 'permission_id': pid, 'granted_at': now}
             for r, ids in role_perms.items() for pid in ids]
        )

    def _initialize_train_schedules(self):
        trains = [
            {'train_id':'TRN001','train_name':'Vellore Express','train_number':'12652','origin':'Vellore','destination':'Chennai','departure_time':'06:00','arrival_time':'09:30','duration':'3h 30m','seats_available':45,'fare':350,'train_type':'Express'},
            {'train_id':'TRN002','train_name':'Katpadi Fast','train_number':'16058','origin':'Vellore','destination':'Chennai','departure_time':'14:20','arrival_time':'17:45','duration':'3h 25m','seats_available':32,'fare':280,'train_type':'Fast Passenger'},
            {'train_id':'TRN003','train_name':'Chennai Mail','train_number':'12602','origin':'Vellore','destination':'Chennai','departure_time':'21:15','arrival_time':'00:45','duration':'3h 30m','seats_available':28,'fare':420,'train_type':'Mail'},
        ]
        self.trains_df = pd.DataFrame(trains, columns=self.trains_df.columns)

    def _create_default_users(self):
        if not (self.users_df['username'] == 'admin').any():
            self.create_user('admin', 'admin@transport.com', 'admin123', 'super_admin')
        if not (self.users_df['username'] == 'user1').any():
            self.create_user('user1', 'user1@transport.com', 'user123', 'passenger')

    # ---------- public API ----------
    def create_user(self, username: str, email: str, password: str, role: str,
                    department: str = 'Transportation') -> str:
        if self._user_exists(username, email):
            return f"Error: Username '{username}' or email '{email}' already exists"
        user_id = f"USER_{len(self.users_df) + 1:06d}"
        self.users_df.loc[len(self.users_df)] = {
            'user_id': user_id, 'username': username, 'email': email,
            'password_hash': self._hash_password(password), 'role': role,
            'department': department, 'status': 'active', 'created_at': datetime.now(),
            'last_login': None, 'failed_attempts': 0
        }
        self._log_access(user_id, 'USER_CREATE', f'user:{user_id}', 'SUCCESS')
        return f"User {username} created successfully with ID: {user_id}"

    def register_user(self, username: str, email: str, password: str,
                      department: str = 'Transportation') -> str:
        return self.create_user(username, email, password, 'passenger', department)

    def authenticate_user(self, username: str, password: str, ip_address: str = '') -> Dict:
        matches = self.users_df[self.users_df['username'] == username]
        if matches.empty:
            return {'success': False, 'message': 'Invalid username or password'}
        u = matches.iloc[0]
        if u['status'] != 'active':
            return {'success': False, 'message': 'Account is not active'}
        if int(u['failed_attempts']) >= 5:
            return {'success': False, 'message': 'Account locked due to too many failed attempts'}
        if self._verify_password(password, u['password_hash']):
            self.users_df.loc[self.users_df['username'] == username, ['failed_attempts','last_login']] = [0, datetime.now()]
            sid = self._create_session(u['user_id'], ip_address)
            self._log_access(u['user_id'], 'LOGIN', 'system', 'SUCCESS', ip_address)
            return {'success': True, 'user_id': u['user_id'], 'username': username,
                    'role': u['role'], 'session_id': sid, 'message': 'Login successful'}
        else:
            fails = int(u['failed_attempts']) + 1
            self.users_df.loc[self.users_df['username'] == username, 'failed_attempts'] = fails
            if fails >= 5:
                self.users_df.loc[self.users_df['username'] == username, 'status'] = 'locked'
            self._log_access(u['user_id'], 'LOGIN', 'system', 'FAILED', ip_address)
            return {'success': False, 'message': 'Invalid username or password'}

    def _create_session(self, user_id: str, ip: str) -> str:
        sid = secrets.token_urlsafe(32)
        self.sessions_df.loc[len(self.sessions_df)] = {
            'session_id': sid, 'user_id': user_id, 'login_time': datetime.now(),
            'logout_time': None, 'ip_address': ip, 'is_active': True
        }
        return sid

    def logout_user(self, session_id: str) -> bool:
        idx = self.sessions_df.index[self.sessions_df['session_id'] == session_id]
        if len(idx) == 0:
            return False
        i = idx[0]
        self.sessions_df.at[i, 'logout_time'] = datetime.now()
        self.sessions_df.at[i, 'is_active'] = False
        uid = self.sessions_df.at[i, 'user_id']
        self._log_access(uid, 'LOGOUT', 'system', 'SUCCESS')
        return True

    def get_user_permissions(self, user_id: str) -> List[str]:
        u = self.users_df[self.users_df['user_id'] == user_id]
        if u.empty:
            return []
        role = u.iloc[0]['role']
        ids = self.role_permissions_df[self.role_permissions_df['role'] == role]['permission_id'].tolist()
        return self.permissions_df[self.permissions_df['permission_id'].isin(ids)]['permission_name'].tolist()

    def search_trains(self, origin: str, destination: str) -> pd.DataFrame:
        return self.trains_df[
            (self.trains_df['origin'].str.lower() == origin.lower()) &
            (self.trains_df['destination'].str.lower() == destination.lower())
        ]

    def book_train_ticket(self, user_id: str, train_id: str, passengers: int = 1) -> Dict:
        t = self.trains_df[self.trains_df['train_id'] == train_id]
        if t.empty:
            return {'success': False, 'message': 'Train not found'}
        row = t.iloc[0]
        seats = int(row['seats_available'])
        if seats < passengers:
            return {'success': False, 'message': f'Only {seats} seats available'}
        idx = t.index[0]
        self.trains_df.at[idx, 'seats_available'] = seats - passengers
        booking_id = f"BKG{datetime.now().strftime('%Y%m%d%H%M%S')}"
        total_fare = int(row['fare']) * passengers
        self._log_access(user_id, 'TRAIN_BOOKING', f"train:{train_id}", 'SUCCESS')
        return {
            'success': True, 'booking_id': booking_id, 'train_id': train_id,
            'train_name': row['train_name'], 'train_number': row['train_number'],
            'origin': row['origin'], 'destination': row['destination'],
            'departure_time': row['departure_time'], 'arrival_time': row['arrival_time'],
            'passengers': passengers, 'total_fare': total_fare,
            'booking_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'Booking confirmed for {passengers} passenger(s) on {row["train_name"]}'
        }

# ----------------- CLI -----------------
def show_train_booking_menu(portal: TransportationPortalAccessManager):
    while portal.current_user:
        user_role = portal.current_user['role']
        username = portal.current_user['username']
        user_id = portal.current_user['user_id']

        print("\n" + "="*50)
        print(f"Welcome, {username}!")
        print("="*50)
        print("1. Search Trains")
        print("2. Book Train Ticket")
        print("3. View My Profile")
        print("4. Logout")

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            print("\n=== SEARCH TRAINS ===")
            print("Available Cities: Vellore, Chennai, Bangalore")
            origin = input("Enter Origin City: ").strip()
            destination = input("Enter Destination City: ").strip()
            if origin.lower() not in ['vellore','chennai','bangalore'] or destination.lower() not in ['vellore','chennai','bangalore']:
                print("❌ Invalid cities. Choose from Vellore, Chennai, Bangalore.")
                continue
            if origin.lower() == destination.lower():
                print("❌ Origin and destination cannot be the same.")
                continue
            trains = portal.search_trains(origin, destination)
            if trains.empty:
                print(f"\n❌ No trains found between {origin} and {destination}")
            else:
                cols = ['train_id','train_name','train_number','departure_time','arrival_time','duration','seats_available','fare','train_type']
                print("\n🚆 AVAILABLE TRAINS")
                print(trains[cols].to_string(index=False))

        elif choice == '2':
            print("\n=== BOOK TRAIN TICKET ===")
            train_id = input("Enter Train ID: ").strip()
            if portal.trains_df.empty or train_id not in portal.trains_df['train_id'].values:
                print("❌ Invalid Train ID. Please check available trains first.")
                continue
            try:
                passengers = int(input("Number of passengers: ").strip())
                if passengers <= 0:
                    print("❌ Passengers must be >= 1.")
                    continue
            except ValueError:
                print("❌ Enter a valid number.")
                continue

            result = portal.book_train_ticket(user_id, train_id, passengers)
            if result['success']:
                print(f"\n✅ {result['message']}")
                print(f"📋 Booking ID: {result['booking_id']}")
                print(f"🚆 Train: {result['train_name']} ({result['train_number']})")
                print(f"📍 Route: {result['origin']} → {result['destination']}")
                print(f"⏰ Departure: {result['departure_time']}")
                print(f"⏰ Arrival: {result['arrival_time']}")
                print(f"👥 Passengers: {result['passengers']}")
                print(f"💰 Total Fare: ₹{result['total_fare']}")
                print(f"📅 Booking Time: {result['booking_time']}")
            else:
                print(f"❌ {result['message']}")

        elif choice == '3':
            print("\n=== MY PROFILE ===")
            print(f"Username: {username}")
            print(f"Role: {user_role}")
            print(f"User ID: {user_id}")
            perms = portal.get_user_permissions(user_id)
            print(f"\nPermissions ({len(perms)}):")
            for p in perms:
                print(f"  ✓ {p}")

        elif choice == '4':
            if portal.current_session:
                portal.logout_user(portal.current_session)
            portal.current_user = None
            portal.current_session = None
            print("👋 You have been logged out successfully.")
            break
        else:
            print("❌ Invalid choice. Please try again.")

def main():
    portal = TransportationPortalAccessManager()
    print("🚆 Welcome to Train Booking System 🚆")
    print("📍 Available Routes: Vellore ⇄ Chennai ⇄ Bangalore")

    while True:
        if portal.current_user is None:
            print("\n" + "="*50)
            print("1. Login")
            print("2. Signup")
            print("3. Exit")
            print("="*50)
            choice = input("Enter your choice (1-3): ").strip()

            if choice == '1':
                print("\n--- Login ---")
                username = input("Username: ").strip()
                password = getpass.getpass("Password: ").strip()
                auth = portal.authenticate_user(username, password, "127.0.0.1")
                if auth['success']:
                    portal.current_user = auth
                    portal.current_session = auth['session_id']
                    print(f"\n✅ {auth['message']}")
                    print(f"Welcome, {auth['username']}!  Role: {auth['role']}")
                    show_train_booking_menu(portal)
                else:
                    print(f"\n❌ {auth['message']}")

            elif choice == '2':
                print("\n--- Signup ---")
                username = input("Choose Username: ").strip()
                email = input("Email: ").strip()
                password = getpass.getpass("Password: ").strip()
                confirm = getpass.getpass("Confirm Password: ").strip()
                if password != confirm:
                    print("❌ Passwords do not match!")
                    continue
                if len(password) < 6:
                    print("❌ Password must be at least 6 characters.")
                    continue
                print("\n" + portal.register_user(username, email, password))

            elif choice == '3':
                print("Thank you for using Train Booking System. Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please try again.")
        else:
            show_train_booking_menu(portal)

if __name__ == "__main__":
    main()
