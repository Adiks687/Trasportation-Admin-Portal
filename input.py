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
# transport_fixed_buses.py
# Transport Booking System — fixes 'buss' bug by using explicit table_map & id_map.
# Resilient: works with or without sqlalchemy/pymysql (optional).
import os
import sys
import mysql.connector
import pandas as pd
from datetime import datetime
import getpass, secrets, time, hashlib, hmac
import binascii
import shutil
import subprocess
import pydoc
import warnings

# Optional SQLAlchemy/pymysql to avoid pandas DBAPI warning
USE_ENGINE = False
engine = None
try:
    from sqlalchemy import create_engine
    import pymysql  # noqa: F401
    USE_ENGINE = True
except Exception:
    USE_ENGINE = False

# Suppress the pandas DBAPI warning in fallback mode
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=r".*pandas only supports SQLAlchemy connectable.*",
    module=".*pandas.*"
)
warnings.filterwarnings("ignore", category=UserWarning, module="pandas.*")

# ---------- CONFIG ----------
DB_NAME = os.getenv("DB_NAME", "transport_system")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")

if not DB_PASS:
    DB_PASS = getpass.getpass("Enter DB password: ")

# ---------- mapping fixes ----------
table_map = {'train': 'trains', 'flight': 'flights', 'bus': 'buses', 'cab': 'cabs'}
id_map = {'train': 'train_id', 'flight': 'flight_id', 'bus': 'bus_id', 'cab': 'cab_id'}

# ---------- mysql-connector helper ----------
def get_mysql_conn(select_db=True):
    try:
        if select_db:
            return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=False)
        else:
            return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, autocommit=False)
    except mysql.connector.Error as e:
        print(" Could not connect to MySQL server:", e)
        sys.exit(1)

# ---------- Ensure DB & tables ----------
def ensure_database_and_tables():
    conn = get_mysql_conn(select_db=False)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET 'utf8mb4'")
    cur.execute(f"USE {DB_NAME}")

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
    conn.commit()

    # seed sample data if empty (non-destructive)
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
        conn.commit()

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
        conn.commit()

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
        conn.commit()

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
        conn.commit()

    cur.close()
    conn.close()

# ---------- password helpers ----------
def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"{iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(password: str, stored: str) -> bool:
    if not stored or not isinstance(stored, str):
        return False
    if '$' in stored:
        try:
            parts = stored.split('$')
            if len(parts) != 3:
                return False
            iterations = int(parts[0])
            salt = binascii.unhexlify(parts[1])
            expected = binascii.unhexlify(parts[2])
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
    if ':' in stored:
        try:
            h, salt = stored.split(':', 1)
            calc = hashlib.sha256((password + salt).encode()).hexdigest()
            return hmac.compare_digest(calc, h)
        except Exception:
            return False
    return False

# ---------- pager helper ----------
def _page_text(text: str):
    try:
        less = shutil.which("less")
        if less:
            proc = subprocess.Popen([less, "-R", "-S"], stdin=subprocess.PIPE)
            try:
                proc.communicate(text.encode("utf-8", errors="replace"))
            except KeyboardInterrupt:
                proc.terminate()
        else:
            pydoc.pager(text)
    except Exception:
        print(text)

# ---------- mask email ----------
def _mask_email(e: str) -> str:
    if not e or "@" not in e:
        return e or ""
    name, domain = e.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*"
    else:
        masked = name[0] + "*" * (len(name)-2) + name[-1]
    return f"{masked}@{domain}"

# ---------- verbose DB preview ----------
def show_all_data_verbose(conn, db_name, max_preview_rows=50):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
            (db_name,)
        )
        tables = [r[0] for r in cur.fetchall()]
    finally:
        cur.close()

    if not tables:
        print(f"No tables found in database `{db_name}`.")
        return

    total = len(tables)
    for i, table in enumerate(tables, start=1):
        print(f"\n--- [{i}/{total}] TABLE: `{db_name}`.`{table}` ---")
        sql = f"SELECT * FROM `{db_name}`.`{table}` LIMIT {max_preview_rows + 1}"
        try:
            if USE_ENGINE and engine is not None:
                df = pd.read_sql(sql, engine)
            else:
                df = pd.read_sql(sql, conn)
        except Exception as e:
            print(f"(error reading table `{table}`: {e})")
            continue

        try:
            cur2 = conn.cursor()
            try:
                cur2.execute("SELECT COUNT(*) FROM `%s`.`%s`" % (db_name, table))
                total_rows = cur2.fetchone()[0]
            except Exception:
                total_rows = None
            finally:
                cur2.close()
        except Exception:
            total_rows = None

        if total_rows is not None:
            print(f"Rows in table: {total_rows}")
        if df.empty:
            print("(table is empty)")
            continue

        more_flag = False
        if len(df) > max_preview_rows:
            more_flag = True
            preview_df = df.iloc[:max_preview_rows]
        else:
            preview_df = df

        money_like = [c for c in preview_df.columns if any(k in c.lower() for k in ("fare", "amount", "total", "refund", "price"))]
        for c in money_like:
            try:
                preview_df[c] = preview_df[c].apply(lambda x: (f"₹{float(x):.2f}" if pd.notnull(x) else ""))
            except Exception:
                pass
        dt_like = [c for c in preview_df.columns if any(k in c.lower() for k in ("time", "date", "at"))]
        for c in dt_like:
            try:
                preview_df[c] = preview_df[c].astype(str)
            except Exception:
                pass

        if 'email' in preview_df.columns:
            preview_df['email'] = preview_df['email'].apply(_mask_email)

        try:
            print(preview_df.to_string(index=False))
        except Exception:
            print(preview_df.head(10).to_string(index=False))
        if more_flag:
            print(f"... (showing {max_preview_rows} rows, more exist)")
        print("-" * 60)

def choose_and_show_database_verbose(conn):
    cur = conn.cursor()
    try:
        cur.execute("SHOW DATABASES")
        dbs = [r[0] for r in cur.fetchall()]
    finally:
        cur.close()

    if not dbs:
        print("No databases found.")
        return

    print("\nAvailable databases:")
    for i, name in enumerate(dbs, start=1):
        print(f"{i}) {name}")
    print("a) View all databases (verbose)")
    print("q) Cancel")

    sel = input("Choose database number, 'a' to view all, or 'q' to cancel: ").strip().lower()
    if sel == 'q':
        print("Cancelled.")
        return
    if sel == 'a':
        for name in dbs:
            print(f"\n\n==== DATABASE: {name} ====")
            show_all_data_verbose(conn, name)
        return
    try:
        idx = int(sel)
    except ValueError:
        print("Invalid selection.")
        return
    if idx < 1 or idx > len(dbs):
        print("Selection out of range.")
        return
    chosen = dbs[idx - 1]
    print(f"\n==== Showing database: {chosen} ====")
    show_all_data_verbose(conn, chosen)

# ---------- Core class ----------
class TransportPortal:
    def __init__(self, conn):
        self.conn = conn

    def register(self, username, email, password, role="passenger"):
        cur = self.conn.cursor()
        cur.execute("SELECT username FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            print(" Username already exists.")
            cur.close()
            return
        try:
            ph = hash_password(password)
            cur.execute("""
                INSERT INTO users(username,email,password_hash,role,status,created_at,last_login)
                VALUES(%s,%s,%s,%s,'active',NOW(),NULL)
            """, (username, email, ph, role))
            self.conn.commit()
            print(" Registered successfully!")
        except Exception as e:
            self.conn.rollback()
            print(" Error registering user:", e)
        finally:
            cur.close()

    def login(self, username, password):
        username = (username or "").strip()
        print(f"DEBUG: attempting login for username: '{username}'")

        cur = self.conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            u = cur.fetchone()
        finally:
            try:
                cur.close()
            except:
                pass

        if not u:
            print("DEBUG: user row not found.")
            cur_ins = self.conn.cursor()
            try:
                cur_ins.execute("INSERT INTO login_history(username,status,time) VALUES(%s,'fail',NOW())", (username,))
                self.conn.commit()
            finally:
                try:
                    cur_ins.close()
                except:
                    pass
            print(" Invalid username or password")
            return None

        stored_hash = u.get('password_hash')
        if stored_hash is None:
            print("DEBUG: stored password_hash is NULL")
        else:
            print(f"DEBUG: stored_hash (len={len(stored_hash)}): {repr(stored_hash[:60] + ('...' if len(stored_hash)>60 else ''))}")
            if '$' in stored_hash:
                print("DEBUG: detected format = PBKDF2 (iterations$salt$hash)")
            elif ':' in stored_hash:
                print("DEBUG: detected format = legacy-sha256 (hash:salt)")
            else:
                print("DEBUG: detected format = unknown")

        ok = False
        matched_branch = None
        try:
            if stored_hash and ('$' in stored_hash):
                try:
                    parts = stored_hash.split('$')
                    if len(parts) == 3:
                        iterations = int(parts[0])
                        salt = binascii.unhexlify(parts[1])
                        expected = binascii.unhexlify(parts[2])
                        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
                        if hmac.compare_digest(dk, expected):
                            ok = True
                            matched_branch = "pbkdf2"
                except Exception as e:
                    print("DEBUG: pbkdf2 check raised:", e)
            if not ok and stored_hash and (':' in stored_hash):
                try:
                    h, salt = stored_hash.split(':', 1)
                    calc = hashlib.sha256((password + salt).encode()).hexdigest()
                    if hmac.compare_digest(calc, h):
                        ok = True
                        matched_branch = "legacy_sha256"
                except Exception as e:
                    print("DEBUG: legacy check raised:", e)
        except Exception as e:
            print("DEBUG: verification outer exception:", e)
            ok = False

        print(f"DEBUG: verification result -> ok={ok}, matched_branch={matched_branch}")

        if not ok:
            cur_ins = self.conn.cursor()
            try:
                cur_ins.execute("INSERT INTO login_history(username,status,time) VALUES(%s,'fail',NOW())", (username,))
                self.conn.commit()
            finally:
                try:
                    cur_ins.close()
                except:
                    pass
            print(" Invalid username or password")
            return None

        if matched_branch == "legacy_sha256":
            try:
                new_hash = hash_password(password)
                upd = self.conn.cursor()
                upd.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, u['user_id']))
                self.conn.commit()
                try:
                    upd.close()
                except:
                    pass
                print("DEBUG: legacy hash upgraded to PBKDF2 in DB.")
            except Exception as e:
                print("DEBUG: failed to upgrade legacy hash:", e)

        cur_upd = self.conn.cursor()
        try:
            cur_upd.execute("UPDATE users SET last_login=NOW() WHERE username=%s", (username,))
            cur_upd.execute("INSERT INTO login_history(username,status,time) VALUES(%s,'success',NOW())", (username,))
            self.conn.commit()
            print(f" Welcome, {username}!")
            return u
        finally:
            try:
                cur_upd.close()
            except:
                pass

    def show_full_table(self, mode):
        # use table_map to avoid plurals bug
        table = table_map.get(mode, f"{mode}s")
        try:
            if USE_ENGINE and engine is not None:
                df = pd.read_sql(f"SELECT * FROM {table} ORDER BY departure_time", engine)
            else:
                df = pd.read_sql(f"SELECT * FROM {table} ORDER BY departure_time", self.conn)
        except Exception as e:
            print("Error reading table:", e)
            return pd.DataFrame()
        if df.empty:
            print("(no records)")
            return df
        print(f"\n📋 FULL {mode.upper()} TABLE:")
        cols_order = [c for c in ['train_id','flight_id','bus_id','cab_id','train_name','airline','operator','provider',
                                  'train_number','flight_number','bus_class','route','origin','destination',
                                  'departure_time','arrival_time','duration','seats_available','fare'] if c in df.columns]
        remaining = [c for c in df.columns if c not in cols_order]
        df = df[cols_order + remaining]
        if 'fare' in df.columns:
            df['fare'] = df['fare'].apply(lambda x: f"₹{x:.2f}")
        print(df.to_string(index=False))
        return df

    def search(self, mode, origin, destination):
        cur = self.conn.cursor(dictionary=True)
        table = table_map.get(mode, f"{mode}s")
        origin_param = f"%{origin.strip()}%"
        dest_param = f"%{destination.strip()}%"
        sql = f"SELECT * FROM {table} WHERE LOWER(origin) LIKE LOWER(%s) AND LOWER(destination) LIKE LOWER(%s) ORDER BY departure_time"
        cur.execute(sql, (origin_param, dest_param))
        rows = cur.fetchall()
        cur.close()
        return rows

    def book(self, mode, service_id, user, passengers, meal=None, payment_mode="UPI"):
        table = table_map.get(mode, f"{mode}s")
        id_col = id_map.get(mode, f"{mode}_id")
        cur = self.conn.cursor(dictionary=True)
        cur.execute(f"SELECT * FROM {table} WHERE {id_col}=%s", (service_id,))
        s = cur.fetchone()
        cur.close()
        if not s:
            print(" Service not found. Make sure you entered the exact ID.")
            return
        if int(s['seats_available']) < int(passengers):
            print(" Not enough seats available.")
            return
        total = float(s['fare']) * int(passengers)
        try:
            upd = self.conn.cursor()
            upd.execute(f"UPDATE {table} SET seats_available=seats_available-%s WHERE {id_col}=%s", (passengers, service_id))
            ins = self.conn.cursor()
            ins.execute("""
                INSERT INTO bookings(user_id,mode,service_id,name,number,origin,destination,departure_time,arrival_time,
                    duration,passengers,meal_type,payment_mode,status,total_fare,booked_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            """, (
                user['user_id'], mode.lower(), service_id,
                s.get('train_name') or s.get('airline') or s.get('operator') or s.get('provider'),
                s.get('train_number') or s.get('flight_number') or s.get('bus_class') or s.get('route'),
                s['origin'], s['destination'], s['departure_time'], s['arrival_time'],
                s.get('duration'), passengers, meal, payment_mode, 'booked', total
            ))
            self.conn.commit()
            print(f" {mode.capitalize()} booked — Booking amount: ₹{total:.2f}")
        except Exception as e:
            self.conn.rollback()
            print(" Error booking service:", e)
        finally:
            try:
                upd.close()
            except:
                pass
            try:
                ins.close()
            except:
                pass

    def cancel_booking(self, user):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM bookings WHERE user_id=%s AND status=%s ORDER BY booked_at DESC", (user['user_id'], 'booked'))
        rows = cur.fetchall()
        cur.close()
        if not rows:
            print("(no active bookings to cancel)")
            return

        df = pd.DataFrame(rows)
        display_cols = ['booking_id','mode','service_id','name','origin','destination','departure_time','arrival_time','passengers','total_fare','booked_at']
        available = [c for c in display_cols if c in df.columns]
        df = df[available].copy()
        if 'total_fare' in df.columns:
            df['total_fare'] = df['total_fare'].apply(lambda x: f"₹{x:.2f}")
        if 'booked_at' in df.columns:
            df['booked_at'] = df['booked_at'].astype(str)
        df.index = range(1, len(df) + 1)
        print("\n🧾 Your ACTIVE Bookings (pick a # to cancel):")
        print(df.to_string())

        sel_in = input("\nEnter booking NUMBER to cancel (leftmost index), or 'q' to abort: ").strip()
        if sel_in.lower() == 'q':
            print("Cancellation aborted.")
            return
        try:
            sel_idx = int(sel_in)
        except ValueError:
            print(" Invalid selection.")
            return
        if sel_idx < 1 or sel_idx > len(rows):
            print(" Selection out of range.")
            return

        sel = rows[sel_idx - 1]
        bid = sel['booking_id']
        fare = float(sel.get('total_fare') or 0)
        refund = round(fare * 0.80, 2)  # 80% refund
        passengers = int(sel.get('passengers') or 0)
        mode = (sel.get('mode') or '').lower()
        service_id = sel.get('service_id')

        table = table_map.get(mode, f"{mode}s")
        id_col = id_map.get(mode, f"{mode}_id")

        try:
            if table and id_col:
                upd = self.conn.cursor()
                upd.execute(f"UPDATE {table} SET seats_available = seats_available + %s WHERE {id_col} = %s", (passengers, service_id))
                upd.close()
            upb = self.conn.cursor()
            upb.execute("UPDATE bookings SET status=%s, refund_amount=%s, cancelled_at=%s WHERE booking_id=%s",
                        ('cancelled', refund, datetime.now(), bid))
            upb.close()
            self.conn.commit()
            print(f" Booking #{bid} cancelled. Refund: ₹{refund:.2f} (20% cancellation fee retained).")
        except Exception as e:
            self.conn.rollback()
            print(" Error cancelling booking:", e)

    def show_profile(self, user):
        cur = self.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM bookings WHERE user_id=%s ORDER BY booked_at DESC", (user['user_id'],))
        rows = cur.fetchall()
        cur.close()
        if not rows:
            print("(no bookings yet)")
            return
        df = pd.DataFrame(rows)
        cols = ['booking_id','mode','service_id','name','origin','destination','departure_time','arrival_time','passengers','total_fare','status','refund_amount','booked_at','cancelled_at']
        available = [c for c in cols if c in df.columns]
        df = df[available].copy()
        if 'total_fare' in df.columns:
            df['total_fare'] = df['total_fare'].apply(lambda x: f"₹{x:.2f}")
        if 'refund_amount' in df.columns:
            df['refund_amount'] = df['refund_amount'].apply(lambda x: (f"₹{x:.2f}" if pd.notnull(x) else ""))
        for dtcol in ['booked_at','cancelled_at']:
            if dtcol in df.columns:
                df[dtcol] = df[dtcol].astype(str)
        print("\n🧾 Your Bookings (latest first):")
        print(df.to_string(index=False))

# ---------- helper: show route hints ----------
def show_route_hints(conn, mode):
    cur = conn.cursor()
    table = table_map.get(mode, f"{mode}s")
    try:
        cur.execute(f"SELECT DISTINCT origin, destination FROM {table} LIMIT 50")
        pairs = cur.fetchall()
    except Exception:
        pairs = []
    cur.close()
    if pairs:
        print("\nAvailable origin → destination (sample):")
        for o,d in pairs:
            print(f" - {o} → {d}")

# ---------- MAIN ----------
def main():
    # Step 1: create DB & tables (without selecting DB)
    ensure_database_and_tables()

    # Step 2: create SQLAlchemy engine once DB exists (if available)
    global engine, USE_ENGINE
    if USE_ENGINE:
        try:
            engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}", pool_pre_ping=True)
        except Exception as e:
            print("Warning: could not create SQLAlchemy engine:", e)
            engine = None
            USE_ENGINE = False

    # Step 3: open connector that selects DB (fixes "No database selected")
    conn = get_mysql_conn(select_db=True)
    portal = TransportPortal(conn)

    if not USE_ENGINE:
        print("\nNOTE: sqlalchemy/pymysql not available — running fallback mode.")
        print("To use the SQLAlchemy path (recommended), run: pip install sqlalchemy pymysql\n")

    print(" TRANSPORT BOOKING SYSTEM — buses bug fixed")

    while True:
        print("\nMain menu:")
        print("d) Debug: show users")
        print("0) Show signups & bookings")
        print("1) Login")
        print("2) Signup")
        print("3) Choose & show a database (verbose)")
        print("4) Exit")
        choice = input("Choice: ").strip().lower()
        if choice == "d":
            cur = conn.cursor()
            cur.execute("SELECT user_id,username,email,password_hash,created_at FROM users ORDER BY created_at DESC")
            rows = cur.fetchall()
            cur.close()
            print("\n=== USERS DEBUG ===")
            if not rows:
                print("(no users found)")
            else:
                for r in rows:
                    uid, uname, email, ph, created = r
                    ph_preview = "<NULL>" if ph is None else (ph[:40] + "..." if len(ph) > 40 else ph)
                    if ph is None:
                        fmt = "NULL"
                    elif '$' in ph:
                        fmt = "pbkdf2"
                    elif ':' in ph:
                        fmt = "legacy-sha256"
                    else:
                        fmt = "unknown"
                    print(f"id={uid} user='{uname}' email='{email}' created={created} format={fmt} preview='{ph_preview}'")
            print("===================\n")
        elif choice == "0":
            try:
                if USE_ENGINE and engine is not None:
                    df_users = pd.read_sql("SELECT user_id,username,email,role,created_at,last_login FROM users ORDER BY created_at DESC", engine)
                else:
                    df_users = pd.read_sql("SELECT user_id,username,email,role,created_at,last_login FROM users ORDER BY created_at DESC", conn)
                if df_users.empty:
                    print("No users.")
                else:
                    df_users['email'] = df_users['email'].apply(_mask_email)
                    for dt in ['created_at','last_login']:
                        if dt in df_users.columns:
                            df_users[dt] = df_users[dt].astype(str)
                    print("\n--- USERS ---")
                    print(df_users.to_string(index=False))
            except Exception as e:
                print("Error fetching users:", e)

            try:
                sql = "SELECT b.booking_id,u.username,b.mode,b.service_id,b.origin,b.destination,b.total_fare,b.status,b.booked_at FROM bookings b LEFT JOIN users u ON u.user_id=b.user_id ORDER BY b.booked_at DESC"
                if USE_ENGINE and engine is not None:
                    df_b = pd.read_sql(sql, engine)
                else:
                    df_b = pd.read_sql(sql, conn)
                if df_b.empty:
                    print("\nNo bookings.")
                else:
                    df_b['total_fare'] = df_b['total_fare'].apply(lambda x: f"₹{float(x):.2f}" if pd.notnull(x) else "")
                    for dt in ['booked_at']:
                        if dt in df_b.columns:
                            df_b[dt] = df_b[dt].astype(str)
                    print("\n--- BOOKINGS ---")
                    print(df_b.to_string(index=False))
            except Exception as e:
                print("Error fetching bookings:", e)
        elif choice == "1":
            username = input("Username: ").strip()
            pwd = getpass.getpass("Password: ").strip()
            user = portal.login(username, pwd)
            if not user:
                continue
            # logged in: full menu
            while True:
                print("\nChoose:")
                print("1) Train")
                print("2) Flight")
                print("3) Bus")
                print("4) Cab")
                print("5) My Bookings")
                print("6) Cancel Booking")
                print("7) Show all databases (verbose)")
                print("8) Logout")
                op = input("Select: ").strip()
                if op in ["1","2","3","4"]:
                    mapping = {"1":"train","2":"flight","3":"bus","4":"cab"}
                    mode = mapping[op]
                    portal.show_full_table(mode)
                    origin = input("\nOrigin (partial ok): ").strip()
                    destination = input("Destination (partial ok): ").strip()
                    results = portal.search(mode, origin, destination)
                    if not results:
                        print(" No matching services found for that route.")
                        show_route_hints(conn, mode)
                        continue
                    df = pd.DataFrame(results)
                    id_col = id_map.get(mode, f"{mode}_id")
                    preferred_cols = [id_col,
                                      'train_name','airline','operator','provider',
                                      'train_number','flight_number','bus_class','route',
                                      'origin','destination','departure_time','arrival_time','duration',
                                      'seats_available','fare']
                    available_cols = [c for c in preferred_cols if c in df.columns]
                    if id_col not in available_cols and len(df.columns)>0:
                        available_cols.insert(0, df.columns[0])
                    for must in ['seats_available','fare']:
                        if must in df.columns and must not in available_cols:
                            available_cols.append(must)
                    if 'fare' in df.columns:
                        df['fare'] = df['fare'].apply(lambda x: f"₹{x:.2f}")
                    print("\n📋 Matched services (ID on left):")
                    print(df[available_cols].to_string(index=False))
                    sid = input(f"\nEnter exact {mode.capitalize()} ID from the leftmost column: ").strip()
                    try:
                        pax = int(input("Passengers: ").strip())
                    except ValueError:
                        print(" Invalid passenger number.")
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
                    choose_and_show_database_verbose(conn)
                elif op == "8":
                    print(" Logged out.")
                    break
                else:
                    print("Invalid selection.")
        elif choice == "2":
            uname = input("Choose username: ").strip()
            email = input("Email: ").strip()
            pwd = getpass.getpass("Password: ").strip()
            portal.register(uname, email, pwd)
        elif choice == "3":
            choose_and_show_database_verbose(conn)
        elif choice == "4":
            print("Goodbye ")
            break
        else:
            print("Invalid choice.")

    try:
        conn.close()
    except:
        pass

if __name__ == "__main__":
    main()
