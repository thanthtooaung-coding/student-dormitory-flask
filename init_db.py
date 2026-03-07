import sqlite3

connection = sqlite3.connect("database/data.db")

cursor = connection.cursor()

# Student table
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    faculty TEXT,
    major TEXT
)
""")

# DormManager table
cursor.execute("""
CREATE TABLE IF NOT EXISTS dorm_managers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    password TEXT,
    phone_number TEXT,
    line_id TEXT
)
""")

# Hostel table
cursor.execute("""
CREATE TABLE IF NOT EXISTS hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    distance_from_campus REAL,
    rating REAL
)
""")

# Room table
cursor.execute("""
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id INTEGER NOT NULL,
    room_type TEXT NOT NULL,
    price REAL NOT NULL,
    facilities TEXT,
    available INTEGER DEFAULT 1,
    FOREIGN KEY (hostel_id) REFERENCES hostels(id)
)
""")

# Booking table
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    checkin_date TEXT NOT NULL,
    booking_status TEXT DEFAULT 'pending',
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
)
""")

# Payment table
cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT DEFAULT 'pending',
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
)
""")

# Bill table
cursor.execute("""
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# Parcel table
cursor.execute("""
CREATE TABLE IF NOT EXISTS parcels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    arrival_date TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# FacilityBooking table
cursor.execute("""
CREATE TABLE IF NOT EXISTS facility_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    facility_name TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# RepairRequest table
cursor.execute("""
CREATE TABLE IF NOT EXISTS repair_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    issue_type TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    report_date TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# Visitor table
cursor.execute("""
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    visitor_name TEXT NOT NULL,
    visit_date TEXT NOT NULL,
    visit_time TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# Chat Messages table
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    sender TEXT DEFAULT 'student',
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

# Admin table
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone_number TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Insert sample dorm manager
try:
    cursor.execute("""
        INSERT OR IGNORE INTO dorm_managers (manager_id, name, email, password, phone_number, line_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        'MGR001',
        'Dorm Manager',
        'manager@kmitl.ac.th',
        'manager123',
        '02-XXX-XXXX',
        '@dormmanager'
    ))
except sqlite3.IntegrityError:
    pass

# Insert sample admin
try:
    cursor.execute("""
        INSERT OR IGNORE INTO admins (admin_id, name, email, password, phone_number)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'ADMIN001',
        'System Admin',
        'admin@kmitl.ac.th',
        'admin123',
        '02-XXX-XXXX'
    ))
except sqlite3.IntegrityError:
    pass

connection.commit()
connection.close()

print("Database created successfully!")
print("Manager login credentials:")
print("Email: manager@kmitl.ac.th")
print("Password: manager123")
print("\nAdmin login credentials:")
print("Email: admin@kmitl.ac.th")
print("Password: admin123")
