# =====================  Transportation Booking System (Single File)  =====================
# Features:
# - Users: signup/login
# - Modes: Train (meals), Flight (meals), Bus, Cab
# - Shows route table first, then schedule table, then booking
# - Profile option shows user info + booking history (table)
# - Major cities seeded across modes
# - FIX: login returns dict (not pandas Series)

import pandas as pd
from datetime import datetime
import hashlib, secrets
import getpass

MEAL_OPTIONS = {"veg", "non-veg", "jain"}

# ---------- Table Printer ----------
def print_table(df: pd.DataFrame, title: str = ""):
    if title:
        print(f"\n{title}")
    if df.empty:
        print("(no data)")
        return
    print(df.to_string(index=False))

def divider():
    print("\n" + "—" * 70)

def ask_meal_if_available(meals_available: bool):
    if not meals_available:
        return None
    print("\n🍽️  Meal options: Veg / Non-Veg / Jain")
    meal = input("Choose meal type (press Enter to skip): ").strip().lower()
    if meal == "":
        return None
    if meal not in MEAL_OPTIONS:
        print("❌ Invalid meal type. Skipping meal.")
        return None
    return meal


# ============= MAIN CLASS WITH ALL DATA + AUTH + BOOKING =============
class TransportationPortalAccessManager:
    def __init__(self):

        # USERS
        self.users_df = pd.DataFrame(columns=[
            'user_id','username','email','password_hash','role','status','created_at','last_login','failed_attempts'
        ])

        # BOOKINGS (unified history)
        self.bookings_df = pd.DataFrame(columns=[
            'booking_id','user_id','mode','service_id','name','number','origin','destination',
            'departure_time','arrival_time','duration','passengers','meal_type','total_fare','booked_at'
        ])

        # TRAINS inventory
        self.trains_df = pd.DataFrame(columns=[
            'train_id','train_name','train_number','origin','destination','departure_time','arrival_time','duration',
            'seats_available','fare','train_type','meals_available'
        ])

        # FLIGHTS inventory
        self.flights_df = pd.DataFrame(columns=[
            'flight_id','airline','flight_number','origin','destination','departure_time','arrival_time','duration',
            'seats_available','fare','aircraft','meals_available'
        ])

        # BUSES inventory
        self.buses_df = pd.DataFrame(columns=[
            'bus_id','operator','bus_class','origin','destination','departure_time','arrival_time','duration',
            'seats_available','fare'
        ])

        # CABS inventory (kept Vellore ↔ Chennai per original requirement)
        self.cabs_df = pd.DataFrame(columns=[
            'cab_id','provider','route','origin','destination','departure_time','arrival_time','duration',
            'seats_available','fare','car_type'
        ])

        self.current_user = None
        self.current_session = None

        self.seed_users()
        self.seed_trains()
        self.seed_flights()
        self.seed_buses()
        self.seed_cabs()

    # -------- Password helpers --------
    def _hash(self,p):
        salt = secrets.token_hex(16)
        return hashlib.sha256((p+salt).encode()).hexdigest()+":"+salt

    def _verify(self,p,stored):
        try:
            h,salt = stored.split(":")
            return hashlib.sha256((p+salt).encode()).hexdigest()==h
        except:
            return False

    # -------- USERS --------
    def seed_users(self):
        self.register("admin","admin@x.com","admin123",role="admin")
        self.register("user1","user1@x.com","user123",role="passenger")

    def register(self,username,email,password,role="passenger"):
        if (self.users_df['username']==username).any():
            return "User exists"
        uid=f"USER_{len(self.users_df)+1:04d}"
        self.users_df.loc[len(self.users_df)] = [
            uid,username,email,self._hash(password),role,"active",datetime.now(),None,0
        ]
        return f"{username} registered"

    def login(self,u,p):
        """Return dict on success, None on failure (avoids Series truthiness bug)."""
        df=self.users_df[self.users_df['username']==u]
        if df.empty:
            return None
        row=df.iloc[0]
        if self._verify(p,row['password_hash']):
            self.users_df.loc[self.users_df['username']==u,'last_login']=datetime.now()
            return row.to_dict()
        return None

    # ====== SEED DATA (TRAINS / FLIGHTS / BUS / CAB) ======

    def seed_trains(self):
        # Major-city routes (sample timings each way)
        trains = [
            # Chennai hub
            ("TRN-CHE-BLR-0600","Chennai Express","12610","Chennai","Bangalore","06:00","11:00","5h00m",80,520,"Express",True),
            ("TRN-CHE-BLR-1400","Chennai Express","12612","Chennai","Bangalore","14:00","19:05","5h05m",80,540,"Express",True),
            ("TRN-BLR-CHE-0700","Brindavan Exp","12639","Bangalore","Chennai","07:00","12:05","5h05m",80,530,"Express",True),

            ("TRN-CHE-HYD-1700","Chennai–Hyd Exp","12759","Chennai","Hyderabad","17:00","06:00","13h00m",60,850,"Express",True),
            ("TRN-HYD-CHE-1800","Hyd–Chennai Exp","12760","Hyderabad","Chennai","18:00","07:00","13h00m",60,850,"Express",True),

            ("TRN-CHE-CBE-0610","Kovai Exp","12679","Chennai","Coimbatore","06:10","11:35","5h25m",90,600,"Express",True),
            ("TRN-CBE-CHE-1710","Kovai Exp","12680","Coimbatore","Chennai","17:10","22:35","5h25m",90,600,"Express",True),

            # Bangalore hub
            ("TRN-BLR-HYD-2100","BLR–HYD SF","22691","Bangalore","Hyderabad","21:00","06:30","9h30m",70,700,"Superfast",True),
            ("TRN-HYD-BLR-2130","HYD–BLR SF","22692","Hyderabad","Bangalore","21:30","07:00","9h30m",70,700,"Superfast",True),

            ("TRN-BLR-CBE-0800","KSR–CBE Intercity","12678","Bangalore","Coimbatore","08:00","12:30","4h30m",80,580,"Intercity",True),
            ("TRN-CBE-BLR-1500","CBE–KSR Intercity","12677","Coimbatore","Bangalore","15:00","19:30","4h30m",80,580,"Intercity",True),

            # Mumbai / Ahmedabad
            ("TRN-MUM-AHM-2230","Gujarat Mail","12901","Mumbai","Ahmedabad","22:30","06:15","7h45m",100,700,"Mail",True),
            ("TRN-AHM-MUM-2300","Gujarat Mail","12902","Ahmedabad","Mumbai","23:00","06:45","7h45m",100,700,"Mail",True),

            # Delhi / Lucknow
            ("TRN-DEL-LKO-2200","Shatabdi Night","12004","Delhi","Lucknow","22:00","04:30","6h30m",120,900,"Shatabdi",True),
            ("TRN-LKO-DEL-0600","Shatabdi Morning","12003","Lucknow","Delhi","06:00","12:30","6h30m",120,900,"Shatabdi",True),

            # Kolkata / Goa (demonstrative long route)
            ("TRN-KOL-GOA-1300","East–West Exp","22890","Kolkata","Goa","13:00","16:00+1","27h00m",50,1600,"Express",True),
            ("TRN-GOA-KOL-1500","West–East Exp","22891","Goa","Kolkata","15:00","18:00+1","27h00m",50,1600,"Express",True),

            # Vellore pairs retained
            ("TRN-VLR-CHE-0600","Vellore Express","12652","Vellore","Chennai","06:00","09:30","3h30m",45,350,"Express",True),
            ("TRN-CHE-VLR-0730","Vellore Express","12651","Chennai","Vellore","07:30","11:00","3h30m",50,350,"Express",True),
            ("TRN-VLR-BLR-0545","Bangalore Exp","12608","Vellore","Bangalore","05:45","09:15","3h30m",38,450,"Express",True),
        ]
        self.trains_df = pd.DataFrame(trains, columns=self.trains_df.columns)

    def seed_flights(self):
        flights = [
            # Chennai hub
            ("FL-CHE-BLR-0715","IndiGo","6E201","Chennai","Bangalore","07:15","08:20","1h05m",150,3000,"A320",True),
            ("FL-CHE-BLR-1845","Vistara","UK812","Chennai","Bangalore","18:45","19:50","1h05m",150,3350,"A320",True),
            ("FL-BLR-CHE-0930","Air India","AI512","Bangalore","Chennai","09:30","10:35","1h05m",150,3200,"A320",True),

            ("FL-CHE-DEL-0640","Vistara","UK836","Chennai","Delhi","06:40","09:25","2h45m",150,6500,"A321",True),
            ("FL-DEL-CHE-1810","IndiGo","6E396","Delhi","Chennai","18:10","20:55","2h45m",150,6400,"A321",True),

            ("FL-CHE-MUM-1020","Air India","AI671","Chennai","Mumbai","10:20","12:15","1h55m",150,5200,"A320",True),
            ("FL-MUM-CHE-2000","IndiGo","6E622","Mumbai","Chennai","20:00","21:55","1h55m",150,5100,"A320",True),

            ("FL-CHE-HYD-1130","IndiGo","6E515","Chennai","Hyderabad","11:30","12:40","1h10m",150,3600,"A320",True),
            ("FL-HYD-CHE-1700","Vistara","UK775","Hyderabad","Chennai","17:00","18:10","1h10m",150,3700,"A320",True),

            # Bangalore hub
            ("FL-BLR-DEL-0715","Vistara","UK808","Bangalore","Delhi","07:15","09:55","2h40m",150,7000,"A321",True),
            ("FL-DEL-BLR-1900","Air India","AI503","Delhi","Bangalore","19:00","21:40","2h40m",150,6900,"A321",True),

            ("FL-BLR-MUM-0810","IndiGo","6E334","Bangalore","Mumbai","08:10","09:40","1h30m",150,4500,"A320",True),
            ("FL-MUM-BLR-0715","IndiGo","6E520","Mumbai","Bangalore","07:15","08:45","1h30m",150,4550,"A320",True),

            ("FL-BLR-KOL-1015","IndiGo","6E298","Bangalore","Kolkata","10:15","12:45","2h30m",150,5600,"A320",True),
            ("FL-KOL-BLR-1500","Vistara","UK787","Kolkata","Bangalore","15:00","17:30","2h30m",150,5700,"A320",True),

            # Western/Eastern hubs
            ("FL-MUM-DEL-0830","Vistara","UK990","Mumbai","Delhi","08:30","10:40","2h10m",150,5200,"A320",True),
            ("FL-DEL-MUM-2000","Vistara","UK995","Delhi","Mumbai","20:00","22:10","2h10m",150,5300,"A320",True),

            ("FL-AHM-DEL-0700","IndiGo","6E2101","Ahmedabad","Delhi","07:00","08:30","1h30m",150,4100,"A320",True),
            ("FL-DEL-AHM-1800","IndiGo","6E2102","Delhi","Ahmedabad","18:00","19:30","1h30m",150,4100,"A320",True),

            ("FL-GOA-MUM-0900","IndiGo","6E701","Goa","Mumbai","09:00","10:10","1h10m",150,3200,"A320",True),
            ("FL-MUM-GOA-1900","IndiGo","6E702","Mumbai","Goa","19:00","20:10","1h10m",150,3300,"A320",True),
        ]
        self.flights_df = pd.DataFrame(flights, columns=self.flights_df.columns)

    def seed_buses(self):
        buses = [
            # South / West
            ("BUS-CHE-BLR-0630","KPN","Volvo AC","Chennai","Bangalore","06:30","12:00","5h30m",40,1200),
            ("BUS-CHE-BLR-2230","Parveen","AC Sleeper","Chennai","Bangalore","22:30","04:45","6h15m",36,1500),
            ("BUS-BLR-CHE-2300","SRS","AC Sleeper","Bangalore","Chennai","23:00","05:30","6h30m",36,1550),

            ("BUS-CHE-HYD-1930","Orange","Volvo AC","Chennai","Hyderabad","19:30","06:30","11h00m",34,1600),
            ("BUS-HYD-CHE-2015","Morning Star","AC Sleeper","Hyderabad","Chennai","20:15","07:00","10h45m",34,1650),

            ("BUS-BLR-HYD-2100","Orange","Volvo AC","Bangalore","Hyderabad","21:00","06:00","9h00m",34,1400),
            ("BUS-HYD-BLR-2200","VRL","AC Sleeper","Hyderabad","Bangalore","22:00","06:45","8h45m",34,1450),

            ("BUS-MUM-GOA-2000","Paulo","Volvo AC","Mumbai","Goa","20:00","06:30","10h30m",40,1700),
            ("BUS-GOA-MUM-2115","Neeta","AC Sleeper","Goa","Mumbai","21:15","07:30","10h15m",40,1750),

            ("BUS-AHM-MUM-2200","GSRTC","Volvo AC","Ahmedabad","Mumbai","22:00","06:00","8h00m",44,1200),
            ("BUS-MUM-AHM-2230","GSRTC","Volvo AC","Mumbai","Ahmedabad","22:30","06:30","8h00m",44,1200),

            ("BUS-DEL-LKO-2200","UPSRTC","Volvo AC","Delhi","Lucknow","22:00","06:00","8h00m",48,1300),
            ("BUS-LKO-DEL-2230","UPSRTC","Volvo AC","Lucknow","Delhi","22:30","06:30","8h00m",48,1300),

            # Vellore ↔ Chennai
            ("BUS-VLR-CHE-0600","TNSTC","Standard","Vellore","Chennai","06:00","09:30","3h30m",50,250),
            ("BUS-CHE-VLR-1730","TNSTC","Standard","Chennai","Vellore","17:30","21:00","3h30m",50,250),
        ]
        self.buses_df = pd.DataFrame(buses, columns=self.buses_df.columns)

    def seed_cabs(self):
        cabs = [
            ("CAB001","Ola","VLR-MAA","Vellore","Chennai","06:00","09:30","3h30m",3,3200,"Sedan"),
            ("CAB002","Uber","MAA-VLR","Chennai","Vellore","16:00","19:30","3h30m",3,3000,"Hatchback")
        ]
        self.cabs_df = pd.DataFrame(cabs, columns=self.cabs_df.columns)

    # ===== SEARCH =====
    def search(self,df,o,d):
        return df[(df['origin'].str.lower()==o.lower()) & (df['destination'].str.lower()==d.lower())]

    # ===== BOOKING (append to unified bookings_df) =====
    def _record_booking(self, rec: dict):
        self.bookings_df.loc[len(self.bookings_df)] = rec

    def book_train(self,train_id,user,passengers,meal):
        t=self.trains_df[self.trains_df['train_id']==train_id]
        if t.empty: return "❌ Train not found"
        row=t.iloc[0]
        if int(row['seats_available'])<passengers: return "❌ Not enough seats"
        idx=t.index[0]
        self.trains_df.at[idx,'seats_available']=int(row['seats_available'])-passengers
        cost=int(row['fare'])*passengers
        bid=f"BKG-TRN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._record_booking({
            'booking_id': bid,'user_id': user['user_id'],'mode':'Train','service_id': row['train_id'],
            'name': row['train_name'],'number': row['train_number'],'origin': row['origin'],'destination': row['destination'],
            'departure_time': row['departure_time'],'arrival_time': row['arrival_time'],'duration': row['duration'],
            'passengers': passengers,'meal_type': meal,'total_fare': cost,'booked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return f"✅ TRAIN BOOKED — ID {bid} — ₹{cost}" + (f" — Meal: {meal}" if meal else "")

    def book_flight(self,fid,user,passengers,meal):
        f=self.flights_df[self.flights_df['flight_id']==fid]
        if f.empty: return "❌ Flight not found"
        row=f.iloc[0]
        if int(row['seats_available'])<passengers: return "❌ Not enough seats"
        idx=f.index[0]
        self.flights_df.at[idx,'seats_available']=int(row['seats_available'])-passengers
        cost=int(row['fare'])*passengers
        bid=f"BKG-AIR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._record_booking({
            'booking_id': bid,'user_id': user['user_id'],'mode':'Flight','service_id': row['flight_id'],
            'name': row['airline'],'number': row['flight_number'],'origin': row['origin'],'destination': row['destination'],
            'departure_time': row['departure_time'],'arrival_time': row['arrival_time'],'duration': row['duration'],
            'passengers': passengers,'meal_type': meal,'total_fare': cost,'booked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return f"✅ FLIGHT BOOKED — ID {bid} — ₹{cost}" + (f" — Meal: {meal}" if meal else "")

    def book_bus(self,bid_,user,pax):
        b=self.buses_df[self.buses_df['bus_id']==bid_]
        if b.empty: return "❌ Bus not found"
        r=b.iloc[0]
        if int(r['seats_available'])<pax: return "❌ Not enough seats"
        idx=b.index[0]
        self.buses_df.at[idx,'seats_available']=int(r['seats_available'])-pax
        cost=int(r['fare'])*pax
        bid=f"BKG-BUS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._record_booking({
            'booking_id': bid,'user_id': user['user_id'],'mode':'Bus','service_id': r['bus_id'],
            'name': r['operator'],'number': r['bus_class'],'origin': r['origin'],'destination': r['destination'],
            'departure_time': r['departure_time'],'arrival_time': r['arrival_time'],'duration': r['duration'],
            'passengers': pax,'meal_type': None,'total_fare': cost,'booked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return f"✅ BUS BOOKED — ID {bid} — ₹{cost}"

    def book_cab(self,cid,user,pax):
        c=self.cabs_df[self.cabs_df['cab_id']==cid]
        if c.empty: return "❌ Cab not found"
        r=c.iloc[0]
        if int(r['seats_available'])<pax: return "❌ Seats not enough"
        cost=int(r['fare'])  # fixed
        bid=f"BKG-CAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._record_booking({
            'booking_id': bid,'user_id': user['user_id'],'mode':'Cab','service_id': r['cab_id'],
            'name': r['provider'],'number': r['route'],'origin': r['origin'],'destination': r['destination'],
            'departure_time': r['departure_time'],'arrival_time': r['arrival_time'],'duration': r['duration'],
            'passengers': pax,'meal_type': None,'total_fare': cost,'booked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        return f"✅ CAB BOOKED — ID {bid} — ₹{cost}"

    # ===== PROFILE =====
    def get_profile(self, user_id: str):
        user = self.users_df[self.users_df['user_id']==user_id]
        if user.empty:
            return None, pd.DataFrame()
        info = user.iloc[0].to_dict()
        bookings = self.bookings_df[self.bookings_df['user_id']==user_id] \
            .sort_values("booked_at", ascending=False)
        return info, bookings


# =============== MENU HANDLERS (with TABLES) ===============

def handle_train(portal,user):
    divider()
    print("🚆 **TRAINS** • Major cities: Chennai, Bangalore, Delhi, Mumbai, Hyderabad, Kolkata, Ahmedabad, Lucknow, Goa, Coimbatore, Vellore")

    routes = portal.trains_df.groupby(["origin","destination"]).size().reset_index(name="train_count")
    routes = routes.sort_values(["origin","destination"], kind="stable")
    print_table(routes,"📍 Train Routes")

    o=input("\nOrigin: ").strip()
    d=input("Destination: ").strip()

    sched=portal.search(portal.trains_df,o,d)
    if sched.empty:
        print("❌ No trains")
        return

    cols=['train_id','train_name','departure_time','arrival_time','duration','seats_available','fare','meals_available']
    print_table(sched[cols],f"📋 Trains {o} → {d}")

    tid=input("Pick Train ID: ").strip()
    sel = sched[sched['train_id']==tid]
    if sel.empty:
        print("❌ Invalid Train ID.")
        return

    try:
        pax=int(input("Passengers: ").strip())
        if pax<=0:
            print("❌ Passengers must be >= 1.")
            return
    except ValueError:
        print("❌ Enter a valid number.")
        return

    meal=ask_meal_if_available(bool(sel.iloc[0]['meals_available']))
    print(portal.book_train(tid,user,pax,meal))

def handle_flight(portal,user):
    divider()
    print("✈️ **FLIGHTS** • Major cities: Chennai, Bangalore, Delhi, Mumbai, Hyderabad, Kolkata, Ahmedabad, Lucknow, Goa")

    routes = portal.flights_df.groupby(["origin","destination"]).size().reset_index(name="flight_count")
    routes = routes.sort_values(["origin","destination"], kind="stable")
    print_table(routes,"📍 Flight Routes")

    o=input("\nOrigin: ").strip()
    d=input("Destination: ").strip()

    sched=portal.search(portal.flights_df,o,d)
    if sched.empty:
        print("❌ No flights")
        return

    cols=['flight_id','airline','departure_time','arrival_time','duration','seats_available','fare','meals_available']
    print_table(sched[cols],f"📋 Flights {o} → {d}")

    fid=input("Pick Flight ID: ").strip()
    sel = sched[sched['flight_id']==fid]
    if sel.empty:
        print("❌ Invalid Flight ID.")
        return

    try:
        pax=int(input("Passengers: ").strip())
        if pax<=0:
            print("❌ Passengers must be >= 1.")
            return
    except ValueError:
        print("❌ Enter a valid number.")
        return

    meal=ask_meal_if_available(bool(sel.iloc[0]['meals_available']))
    print(portal.book_flight(fid,user,pax,meal))

def handle_bus(portal,user):
    divider()
    print("🚌 **BUSES** • Major cities: Chennai, Bangalore, Delhi, Mumbai, Hyderabad, Kolkata, Ahmedabad, Lucknow, Goa, Coimbatore, Vellore")

    routes = portal.buses_df.groupby(["origin","destination"]).size().reset_index(name="bus_count")
    routes = routes.sort_values(["origin","destination"], kind="stable")
    print_table(routes,"📍 Bus Routes")

    o=input("\nOrigin: ").strip()
    d=input("Destination: ").strip()

    sched=portal.search(portal.buses_df,o,d)
    if sched.empty:
        print("❌ No buses")
        return

    cols=['bus_id','operator','bus_class','departure_time','arrival_time','duration','seats_available','fare']
    print_table(sched[cols],f"📋 Buses {o} → {d}")

    bid=input("Pick Bus ID: ").strip()
    sel = sched[sched['bus_id']==bid]
    if sel.empty:
        print("❌ Invalid Bus ID.")
        return

    try:
        pax=int(input("Passengers: ").strip())
        if pax<=0:
            print("❌ Passengers must be >= 1.")
            return
    except ValueError:
        print("❌ Enter a valid number.")
        return

    print(portal.book_bus(bid,user,pax))

def handle_cab(portal,user):
    divider()
    print("🚖 **CABS (Vellore ↔ Chennai)**")

    routes = portal.cabs_df.groupby(["origin","destination"]).size().reset_index(name="cab_count")
    routes = routes.sort_values(["origin","destination"], kind="stable")
    print_table(routes,"📍 Cab Routes")

    o=input("\nOrigin: ").strip()
    d=input("Destination: ").strip()

    sched=portal.search(portal.cabs_df,o,d)
    if sched.empty:
        print("❌ No cabs")
        return

    cols=['cab_id','provider','car_type','departure_time','arrival_time','duration','seats_available','fare']
    print_table(sched[cols],f"📋 Cabs {o} → {d}")

    cid=input("Pick Cab ID: ").strip()
    sel = sched[sched['cab_id']==cid]
    if sel.empty:
        print("❌ Invalid Cab ID.")
        return

    try:
        pax=int(input("Passengers: ").strip())
        if pax<=0:
            print("❌ Passengers must be >= 1.")
            return
    except ValueError:
        print("❌ Enter a valid number.")
        return

    print(portal.book_cab(cid,user,pax))

def handle_profile(portal, user):
    divider()
    print("🧑‍💼 **MY PROFILE**")
    info, bookings = portal.get_profile(user['user_id'])
    if not info:
        print("No profile found.")
        return
    # Basic info
    print_table(pd.DataFrame([{
        'User ID': info['user_id'],
        'Username': info['username'],
        'Email': info['email'],
        'Role': info['role'],
        'Status': info['status'],
        'Last Login': info['last_login']
    }]), "👤 User Details")
    # Booking history
    cols = ['booking_id','mode','service_id','name','number','origin','destination',
            'departure_time','arrival_time','passengers','meal_type','total_fare','booked_at']
    print_table(bookings[cols], "🧾 Your Bookings (latest first)") if not bookings.empty else print("(no bookings yet)")


# =============== MAIN LOOP ===============

def main():
    portal=TransportationPortalAccessManager()

    print("🌐 MULTI-TRANSPORT BOOKING SYSTEM")
    print("Demo login: user1 / user123")

    while True:
        divider()
        print("1) Login\n2) Signup\n3) Exit")
        ch=input("Choice: ").strip()

        if ch=="1":
            u=input("Username: ").strip()
            p=getpass.getpass("Password: ").strip()
            user=portal.login(u,p)
            if user is None:
                print("❌ Invalid login")
                continue

            print(f"✅ Welcome {user['username']}!")

            while True:
                divider()
                print("1) 🚆 Train\n2) ✈️ Flight\n3) 🚌 Bus\n4) 🚖 Cab\n5) 🧑‍💼 Profile\n6) Logout")
                op=input("Select: ").strip()

                if op=="1": 
                    handle_train(portal,user)
                elif op=="2": 
                    handle_flight(portal,user)
                elif op=="3": 
                    handle_bus(portal,user)
                elif op=="4": 
                    handle_cab(portal,user)
                elif op=="5":
                    handle_profile(portal,user)
                else:
                    break

        elif ch=="2":
            u=input("New username: ").strip()
            e=input("Email: ").strip()
            p=getpass.getpass("Password: ").strip()
            print(portal.register(u,e,p))
        else:
            print("👋 Bye")
            print("------------------------Thank you for using our transportation portal------------------------------")
            break


if __name__=="__main__":
    main()
