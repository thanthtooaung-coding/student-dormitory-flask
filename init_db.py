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

# FacilityBooking table (booking_id = room booking from bookings table)
cursor.execute("""
CREATE TABLE IF NOT EXISTS facility_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    booking_id INTEGER NOT NULL,
    facility_name TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
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

# Visitor table (booking_id = room booking from bookings table)
cursor.execute("""
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    booking_id INTEGER NOT NULL,
    visitor_name TEXT NOT NULL,
    visit_date TEXT NOT NULL,
    visit_time TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
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

# Seed data for facility_bookings and visitors (require student, hostel, room, booking)
try:
    cursor.execute("""
        INSERT OR IGNORE INTO students (student_id, name, email, password, faculty, major)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('STU001', 'Sample Student', 'student@kmitl.ac.th', 'student123', 'Engineering', 'Computer Science'))
except sqlite3.IntegrityError:
    pass

try:
    cursor.execute("""
        INSERT OR IGNORE INTO hostels (name, location, distance_from_campus, rating)
        VALUES (?, ?, ?, ?)
    """, ('Sample Hostel', 'Near Campus', 0.5, 4.5))
except sqlite3.IntegrityError:
    pass

cursor.execute("SELECT id FROM students WHERE student_id = 'STU001' LIMIT 1")
student_row = cursor.fetchone()
cursor.execute("SELECT id FROM hostels WHERE name = 'Sample Hostel' LIMIT 1")
hostel_row = cursor.fetchone()
if student_row and hostel_row:
    student_id = student_row[0]
    hostel_id = hostel_row[0]
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO rooms (hostel_id, room_type, price, facilities, available)
            VALUES (?, ?, ?, ?, ?)
        """, (hostel_id, 'Single', 5000.0, 'WiFi, AC', 1))
    except sqlite3.IntegrityError:
        pass
    cursor.execute("SELECT id FROM rooms WHERE hostel_id = ? LIMIT 1", (hostel_id,))
    room_row = cursor.fetchone()
    if room_row:
        room_id = room_row[0]
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO bookings (student_id, room_id, checkin_date, booking_status)
                VALUES (?, ?, ?, ?)
            """, (student_id, room_id, '2025-06-01', 'confirmed'))
        except sqlite3.IntegrityError:
            pass
        cursor.execute("SELECT id FROM bookings WHERE student_id = ? AND booking_status = 'confirmed' LIMIT 1", (student_id,))
        booking_row = cursor.fetchone()
        if booking_row:
            room_booking_id = booking_row[0]
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO facility_bookings (student_id, booking_id, facility_name, booking_date)
                    VALUES (?, ?, ?, ?)
                """, (student_id, room_booking_id, 'Gym', '2025-06-15'))
            except sqlite3.IntegrityError:
                pass
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO visitors (student_id, booking_id, visitor_name, visit_date, visit_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, room_booking_id, 'John Doe', '2025-06-10', '14:00'))
            except sqlite3.IntegrityError:
                pass
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO bills (student_id, type, amount, due_date, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, 'Monthly Rent', 5000.0, '2025-06-05', 'pending'))
            except sqlite3.IntegrityError:
                pass
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO parcels (student_id, sender, arrival_date, status)
                    VALUES (?, ?, ?, ?)
                """, (student_id, 'Online Store', '2025-06-08', 'pending'))
            except sqlite3.IntegrityError:
                pass

connection.commit()
connection.close()

print("Database created successfully!")
print("Student login credentials:")
print("Email: student@kmitl.ac.th")
print("\nPassword: student123")
print("Manager login credentials:")
print("Email: manager@kmitl.ac.th")
print("Password: manager123")
print("\nAdmin login credentials:")
print("Email: admin@kmitl.ac.th")
print("Password: admin123")
