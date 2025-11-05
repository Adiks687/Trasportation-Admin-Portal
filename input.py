# =====================  Transportation Booking System (Single File)  ===================== 
# Features: 
# - Users: signup/login 
# - Modes: Train (meals), Flight (meals), Bus, Cab 
# - Shows route table first, then schedule table, then booking 
# - Profile option shows user info + booking history (table) 
# - Major cities seeded across modes 
# - FIX: login returns dict (not pandas Series)
# transport_mysql_with_cancel_pretty.py
# MySQL-backed Transport Booking System — prettier booking display + easier cancel
# Refund = 80% (20% cancellation fee). Cancel by selecting the booking row number.

import mysql.connector
import pandas as pd
from datetime import datetime
import getpass, hashlib, secrets, sys, time

# DB config
DB_NAME = "transport_system"
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "Rvnd$321"

# ---------- Server connection and DB setup ----------
def get_server_conn():
    try:
        return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, autocommit=False)
    except mysql.connector.Error as e:
        print("❌ Could not connect to MySQL server:", e)
        sys.exit(1)

def ensure_database_and_tables():
    server = get_server_conn()
    cur = server.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET 'utf8mb4'")
    cur.execute(f"USE {DB_NAME}")

    # create tables if missing (non-destructive)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            email VARCHAR(100),
            password_hash TEXT,
            role VARCHAR(20),
            status VARCHAR(20),
            created_at DATETIME,
            last_login DATETIME
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings(
            booking_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            mode VARCHAR(20),
            service_id VARCHAR(50),
            name VARCHAR(100),
            number VARCHAR(50),
            origin VARCHAR(50),
            destination VARCHAR(50),
            departure_time VARCHAR(20),
            arrival_time VARCHAR(20),
            duration VARCHAR(20),
            passengers INT,
            meal_type VARCHAR(20),
            payment_mode VARCHAR(20),
            status VARCHAR(20),
            total_fare DECIMAL(10,2),
            booked_at DATETIME,
            refund_amount DECIMAL(10,2) NULL,
            cancelled_at DATETIME NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trains(
            train_id VARCHAR(50) PRIMARY KEY,
            train_name VARCHAR(100),
            train_number VARCHAR(20),
            origin VARCHAR(50),
            destination VARCHAR(50),
            departure_time VARCHAR(20),
            arrival_time VARCHAR(20),
            duration VARCHAR(20),
            seats_available INT,
            fare DECIMAL(10,2),
            meals_available BOOLEAN
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flights(
            flight_id VARCHAR(50) PRIMARY KEY,
            airline VARCHAR(50),
            flight_number VARCHAR(20),
            origin VARCHAR(50),
            destination VARCHAR(50),
            departure_time VARCHAR(20),
            arrival_time VARCHAR(20),
            duration VARCHAR(20),
            seats_available INT,
            fare DECIMAL(10,2),
            meals_available BOOLEAN
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS buses(
            bus_id VARCHAR(50) PRIMARY KEY,
            operator VARCHAR(50),
            bus_class VARCHAR(50),
            origin VARCHAR(50),
            destination VARCHAR(50),
            departure_time VARCHAR(20),
            arrival_time VARCHAR(20),
            duration VARCHAR(20),
            seats_available INT,
            fare DECIMAL(10,2)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cabs(
            cab_id VARCHAR(50) PRIMARY KEY,
            provider VARCHAR(50),
            route VARCHAR(50),
            origin VARCHAR(50),
            destination VARCHAR(50),
            departure_time VARCHAR(20),
            arrival_time VARCHAR(20),
            duration VARCHAR(20),
            seats_available INT,
            fare DECIMAL(10,2),
            car_type VARCHAR(50)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_history(
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50),
            status VARCHAR(10),
            time DATETIME
        )
    """)
    server.commit()

    # seed a few rows if empty (non-destructive)
    cur.execute("SELECT COUNT(*) FROM trains")
    if cur.fetchone()[0] == 0:
        trains = [
            ("TRN1","Chennai Express","12610","Chennai","Bangalore","06:00","11:00","5h00m",80,520,1),
            ("TRN2","Chennai Super","12612","Chennai","Bangalore","14:00","19:05","5h05m",70,540,1),
            ("TRN3","Brindavan Exp","12639","Bangalore","Chennai","07:00","12:05","5h05m",75,530,1),
            ("TRN4","Coimbatore Inter","12678","Coimbatore","Bangalore","08:00","12:30","4h30m",60,580,1),
            ("TRN5","Vellore Express","12652","Vellore","Chennai","06:00","09:30","3h30m",45,350,1),
        ]
        cur.executemany("""
            INSERT INTO trains(train_id,train_name,train_number,origin,destination,departure_time,arrival_time,duration,seats_available,fare,meals_available)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, trains)
        server.commit()

    cur.execute("SELECT COUNT(*) FROM flights")
    if cur.fetchone()[0] == 0:
        flights = [
            ("FL1","IndiGo","6E201","Chennai","Bangalore","07:15","08:20","1h05m",150,3000,1),
            ("FL2","Vistara","UK836","Chennai","Delhi","06:40","09:25","2h45m",140,6500,1),
            ("FL3","Air India","AI503","Delhi","Bangalore","19:00","21:40","2h40m",150,6900,1),
            ("FL4","IndiGo","6E334","Bangalore","Mumbai","08:10","09:40","1h30m",150,4500,1),
            ("FL5","IndiGo","6E701","Goa","Mumbai","09:00","10:10","1h10m",120,3200,1),
        ]
        cur.executemany("""
            INSERT INTO flights(flight_id,airline,flight_number,origin,destination,departure_time,arrival_time,duration,seats_available,fare,meals_available)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, flights)
        server.commit()

    cur.execute("SELECT COUNT(*) FROM buses")
    if cur.fetchone()[0] == 0:
        buses = [
            ("BUS1","KPN","Volvo AC","Chennai","Bangalore","06:30","12:00","5h30m",40,1200),
            ("BUS2","Parveen","AC Sleeper","Chennai","Bangalore","22:30","04:45","6h15m",36,1500),
            ("BUS3","SRS","AC Sleeper","Bangalore","Chennai","23:00","05:30","6h30m",36,1550),
            ("BUS4","Orange","Volvo AC","Chennai","Hyderabad","19:30","06:30","11h00m",34,1600),
            ("BUS5","GSRTC","Volvo AC","Ahmedabad","Mumbai","22:00","06:00","8h00m",44,1200),
        ]
        cur.executemany("""
            INSERT INTO buses(bus_id,operator,bus_class,origin,destination,departure_time,arrival_time,duration,seats_available,fare)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, buses)
        server.commit()

    cur.execute("SELECT COUNT(*) FROM cabs")
    if cur.fetchone()[0] == 0:
        cabs = [
            ("CAB1","Ola","VLR-MAA","Vellore","Chennai","06:00","09:30","3h30m",3,3200,"Sedan"),
            ("CAB2","Uber","MAA-VLR","Chennai","Vellore","16:00","19:30","3h30m",3,3000,"Hatchback"),
            ("CAB3","LocalX","BLR-MAA","Bangalore","Chennai","05:30","09:30","4h00m",4,3500,"SUV"),
            ("CAB4","FastGo","CHE-AHM","Chennai","Ahmedabad","10:00","20:00","10h00m",2,8000,"Sedan"),
            ("CAB5","GoCar","DEL-LKO","Delhi","Lucknow","22:00","06:00","8h00m",4,4500,"Sedan"),
        ]
        cur.executemany("""
            INSERT INTO cabs(cab_id,provider,route,origin,destination,departure_time,arrival_time,duration,seats_available,fare,car_type)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, cabs)
        server.commit()

    return server

# ---------- password helpers ----------
def hash_password(p):
    salt = secrets.token_hex(16)
    return hashlib.sha256((p + salt).encode()).hexdigest() + ":" + salt

def verify_password(p, stored):
    try:
        h, salt = stored.split(":")
        return hashlib.sha256((p + salt).encode()).hexdigest() == h
    except:
        return False

# ---------- Core class with nicer displays ----------
class TransportPortal:
    def __init__(self, conn):
        self.conn = conn

    # register/login
    def register(self, username, email, password, role="passenger"):
        cur = self.conn.cursor()
        cur.execute("SELECT username FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            print("❌ Username already exists.")
            return
        cur.execute("""
            INSERT INTO users(username,email,password_hash,role,status,created_at,last_login)
            VALUES(%s,%s,%s,%s,'active',NOW(),NULL)
        """, (username, email, hash_password(password), role))
        self.conn.commit()
        print("✅ Registered successfully!")

    def login(self, username, password):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        u = cur.fetchone()
        if not u or not verify_password(password, u['password_hash']):
            cur_ins = self.conn.cursor()
            cur_ins.execute("INSERT INTO login_history(username,status,time) VALUES(%s,'fail',NOW())", (username,))
            self.conn.commit()
            print("❌ Invalid username or password")
            return None
        cur_upd = self.conn.cursor()
        cur_upd.execute("UPDATE users SET last_login=NOW() WHERE username=%s", (username,))
        cur_upd.execute("INSERT INTO login_history(username,status,time) VALUES(%s,'success',NOW())", (username,))
        self.conn.commit()
        print(f"✅ Welcome, {username}!")
        return u

    # show entire table for a mode
    def show_full_table(self, mode):
        table = f"{mode}s"
        df = pd.read_sql(f"SELECT * FROM {table} ORDER BY departure_time", self.conn)
        if df.empty:
            print("(no records)")
            return df
        print(f"\n📋 FULL {mode.upper()} TABLE:")
        # show the important columns first
        cols_order = [c for c in ['train_id','flight_id','bus_id','cab_id','train_name','airline','operator','provider',
                                  'train_number','flight_number','bus_class','route','origin','destination',
                                  'departure_time','arrival_time','duration','seats_available','fare'] if c in df.columns]
        remaining = [c for c in df.columns if c not in cols_order]
        df = df[cols_order + remaining]
        # format fare
        if 'fare' in df.columns:
            df['fare'] = df['fare'].apply(lambda x: f"₹{x:.2f}")
        print(df.to_string(index=False))
        return df

    # partial, case-insensitive contains search on origin/destination
    def search(self, mode, origin, destination):
        cur = self.conn.cursor(dictionary=True)
        table = f"{mode}s"
        origin_param = f"%{origin.strip()}%"
        dest_param = f"%{destination.strip()}%"
        sql = f"SELECT * FROM {table} WHERE LOWER(origin) LIKE LOWER(%s) AND LOWER(destination) LIKE LOWER(%s) ORDER BY departure_time"
        cur.execute(sql, (origin_param, dest_param))
        return cur.fetchall()

    # book a service by id
    def book(self, mode, service_id, user, passengers, meal=None, payment_mode="UPI"):
        table = f"{mode}s"
        id_col = f"{mode}_id"
        cur = self.conn.cursor(dictionary=True)
        cur.execute(f"SELECT * FROM {table} WHERE {id_col}=%s", (service_id,))
        s = cur.fetchone()
        if not s:
            print("❌ Service not found. Make sure you entered the exact ID.")
            return
        if int(s['seats_available']) < int(passengers):
            print("❌ Not enough seats available.")
            return
        total = float(s['fare']) * int(passengers)
        upd = self.conn.cursor()
        upd.execute(f"UPDATE {table} SET seats_available=seats_available-%s WHERE {id_col}=%s", (passengers, service_id))
        ins = self.conn.cursor()
        ins.execute("""
            INSERT INTO bookings(user_id,mode,service_id,name,number,origin,destination,departure_time,arrival_time,
                duration,passengers,meal_type,payment_mode,status,total_fare,booked_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (
            user['user_id'], mode.capitalize(), service_id,
            s.get('train_name') or s.get('airline') or s.get('operator') or s.get('provider'),
            s.get('train_number') or s.get('flight_number') or s.get('bus_class') or s.get('route'),
            s['origin'], s['destination'], s['departure_time'], s['arrival_time'],
            s.get('duration'), passengers, meal, payment_mode, 'booked', total
        ))
        self.conn.commit()
        print(f"✅ {mode.capitalize()} booked — Booking amount: ₹{total:.2f}")

    # cancel booking (refund 80%) — improved UI: choose by row number
    def cancel_booking(self, user):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM bookings WHERE user_id=%s AND status=%s ORDER BY booked_at DESC", (user['user_id'], 'booked'))
        rows = cur.fetchall()
        if not rows:
            print("(no active bookings to cancel)")
            return

        # Build pretty DataFrame with index numbers
        df = pd.DataFrame(rows)
        display_cols = ['booking_id','mode','service_id','name','origin','destination','departure_time','arrival_time','passengers','total_fare','booked_at']
        available = [c for c in display_cols if c in df.columns]
        df = df[available].copy()
        # format fare and time
        if 'total_fare' in df.columns:
            df['total_fare'] = df['total_fare'].apply(lambda x: f"₹{x:.2f}")
        if 'booked_at' in df.columns:
            df['booked_at'] = df['booked_at'].astype(str)
        # add numbered index for easy selection
        df.index = range(1, len(df) + 1)
        print("\n🧾 Your ACTIVE Bookings (pick a # to cancel):")
        print(df.to_string())

        # ask for selection
        sel_in = input("\nEnter booking NUMBER to cancel (leftmost index), or 'q' to abort: ").strip()
        if sel_in.lower() == 'q':
            print("Cancellation aborted.")
            return
        try:
            sel_idx = int(sel_in)
        except ValueError:
            print("❌ Invalid selection.")
            return
        if sel_idx < 1 or sel_idx > len(rows):
            print("❌ Selection out of range.")
            return

        sel = rows[sel_idx - 1]
        bid = sel['booking_id']
        fare = float(sel.get('total_fare') or 0)
        refund = round(fare * 0.80, 2)  # 80% refund
        passengers = int(sel.get('passengers') or 0)
        mode = (sel.get('mode') or '').lower()
        service_id = sel.get('service_id')

        # map mode to table/id column
        table_map = {'train':'trains','flight':'flights','bus':'buses','cab':'cabs'}
        id_map = {'train':'train_id','flight':'flight_id','bus':'bus_id','cab':'cab_id'}
        table = table_map.get(mode)
        id_col = id_map.get(mode)

        try:
            # restore seats
            if table and id_col:
                upd = self.conn.cursor()
                upd.execute(f"UPDATE {table} SET seats_available = seats_available + %s WHERE {id_col} = %s", (passengers, service_id))
            # update booking status, refund and cancelled time
            upb = self.conn.cursor()
            upb.execute("UPDATE bookings SET status=%s, refund_amount=%s, cancelled_at=%s WHERE booking_id=%s",
                        ('cancelled', refund, datetime.now(), bid))
            self.conn.commit()
            print(f"✅ Booking #{bid} cancelled. Refund: ₹{refund:.2f} (20% cancellation fee retained).")
        except Exception as e:
            self.conn.rollback()
            print("❌ Error cancelling booking:", e)

    # show profile bookings (pretty)
    def show_profile(self, user):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM bookings WHERE user_id=%s ORDER BY booked_at DESC", (user['user_id'],))
        rows = cur.fetchall()
        if not rows:
            print("(no bookings yet)")
            return
        df = pd.DataFrame(rows)
        cols = ['booking_id','mode','service_id','name','origin','destination','departure_time','arrival_time','passengers','total_fare','status','refund_amount','booked_at','cancelled_at']
        available = [c for c in cols if c in df.columns]
        df = df[available].copy()
        # format currency & datetime
        if 'total_fare' in df.columns:
            df['total_fare'] = df['total_fare'].apply(lambda x: f"₹{x:.2f}")
        if 'refund_amount' in df.columns:
            df['refund_amount'] = df['refund_amount'].apply(lambda x: (f"₹{x:.2f}" if pd.notnull(x) else ""))
        for dtcol in ['booked_at','cancelled_at']:
            if dtcol in df.columns:
                df[dtcol] = df[dtcol].astype(str)
        print("\n🧾 Your Bookings (latest first):")
        print(df.to_string(index=False))

# helper: show route hints
def show_route_hints(conn, mode):
    cur = conn.cursor()
    table = f"{mode}s"
    cur.execute(f"SELECT DISTINCT origin, destination FROM {table} LIMIT 50")
    pairs = cur.fetchall()
    if pairs:
        print("\nAvailable origin → destination (sample):")
        for o,d in pairs:
            print(f" - {o} → {d}")

# ---------- MAIN ----------
def main():
    conn = ensure_database_and_tables()
    portal = TransportPortal(conn)
    print("🌐 TRANSPORT BOOKING SYSTEM — prettier booking display + easy cancel")
    print("Tip: enter partial origin/destination (e.g., 'che' will match 'Chennai').")

    while True:
        print("\nMain menu:")
        print("1) Login")
        print("2) Signup")
        print("3) Exit")
        choice = input("Choice: ").strip()
        if choice == "1":
            username = input("Username: ").strip()
            pwd = getpass.getpass("Password: ").strip()
            user = portal.login(username, pwd)
            if not user:
                continue
            # logged in
            while True:
                print("\nChoose:")
                print("1) 🚆 Train")
                print("2) ✈️ Flight")
                print("3) 🚌 Bus")
                print("4) 🚖 Cab")
                print("5) 🧾 My Bookings")
                print("6) ❌ Cancel Booking")
                print("7) Logout")
                op = input("Select: ").strip()
                if op in ["1","2","3","4"]:
                    mapping = {"1":"train","2":"flight","3":"bus","4":"cab"}
                    mode = mapping[op]
                    # show full table first
                    portal.show_full_table(mode)
                    origin = input("\nOrigin (partial ok): ").strip()
                    destination = input("Destination (partial ok): ").strip()
                    results = portal.search(mode, origin, destination)
                    if not results:
                        print("❌ No matching services found for that route.")
                        show_route_hints(conn, mode)
                        continue
                    df = pd.DataFrame(results)
                    id_col = f"{mode}_id"
                    preferred_cols = [id_col,
                                      'train_name','airline','operator','provider',
                                      'train_number','flight_number','bus_class','route',
                                      'origin','destination','departure_time','arrival_time','duration',
                                      'seats_available','fare']
                    available_cols = [c for c in preferred_cols if c in df.columns]
                    if id_col not in available_cols and len(df.columns)>0:
                        available_cols.insert(0, df.columns[0])
                    # ensure seats and fare shown
                    for must in ['seats_available','fare']:
                        if must in df.columns and must not in available_cols:
                            available_cols.append(must)
                    # format fare column before printing if exists
                    if 'fare' in df.columns:
                        df['fare'] = df['fare'].apply(lambda x: f"₹{x:.2f}")
                    print("\n📋 Matched services (ID on left):")
                    print(df[available_cols].to_string(index=False))
                    sid = input(f"\nEnter exact {mode.capitalize()} ID from the leftmost column: ").strip()
                    try:
                        pax = int(input("Passengers: ").strip())
                    except ValueError:
                        print("❌ Invalid passenger number.")
                        continue
                    meal = None
                    if mode in ["train","flight"]:
                        meal = input("Meal (veg/non-veg/jain/none): ").strip().lower() or None
                    portal.book(mode, sid, user, pax, meal)
                elif op == "5":
                    portal.show_profile(user)
                elif op == "6":
                    portal.cancel_booking(user)
                elif op == "7":
                    print("🔒 Logged out.")
                    break
                else:
                    print("Invalid selection.")
        elif choice == "2":
            uname = input("Choose username: ").strip()
            email = input("Email: ").strip()
            pwd = getpass.getpass("Password: ").strip()
            portal.register(uname, email, pwd)
        elif choice == "3":
            print("Goodbye 👋")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()

