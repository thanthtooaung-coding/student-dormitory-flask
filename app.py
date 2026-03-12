from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db_connection
from datetime import datetime, date
from functools import wraps
import sqlite3
import io
import base64

import qrcode

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

PROMPTPAY_ID = "0123456789"  # TODO: replace with your real PromptPay ID/phone


def _tlv(tag, value):
    length = f"{len(value):02d}"
    return f"{tag}{length}{value}"


def _crc16(payload: str) -> str:
    """CRC16-CCITT (0x1021) for PromptPay payload."""
    crc = 0xFFFF
    for ch in payload:
        crc ^= ord(ch) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def generate_promptpay_payload(target_id: str, amount: float, reference: str = "") -> str:
    """
    Build an EMVCo / Thai PromptPay payload including fixed amount.
    `target_id` can be phone (starting with 0) or national ID.
    """
    # Merchant account information (PromptPay)
    aid = _tlv("00", "A000000677010111")

    # Phone number: convert 0XXXXXXXXX -> 66XXXXXXXXX (without leading 0)
    account = target_id
    if account.startswith("0") and len(account) == 10:
        account = "66" + account[1:]

    mai_sub = aid + _tlv("01", account)
    mai = _tlv("29", mai_sub)

    payload = ""
    payload += _tlv("00", "01")        # Payload format indicator
    payload += _tlv("01", "11")        # Dynamic QR
    payload += mai
    payload += _tlv("52", "0000")      # Merchant category code
    payload += _tlv("53", "764")       # Currency: THB

    amount_str = f"{amount:.2f}"
    payload += _tlv("54", amount_str)  # Amount

    payload += _tlv("58", "TH")        # Country
    payload += _tlv("59", "KMITL STAYLINK")[:_tlv("59", "KMITL STAYLINK").find("59")+2+2+25]  # ensure <=25 chars
    payload += _tlv("60", "BANGKOK")   # City

    if reference:
        additional = _tlv("01", reference[:25])
        payload += _tlv("62", additional)

    # Append CRC placeholder and then real CRC
    payload_with_crc = payload + "6304"
    crc = _crc16(payload_with_crc)
    return payload_with_crc + crc


def generate_promptpay_qr_base64(target_id: str, amount: float, reference: str = "") -> str:
    payload = generate_promptpay_payload(target_id, amount, reference)
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")

@app.context_processor
def inject_current_year():
    return dict(current_year=date.today().year)

@app.template_filter('date_str')
def date_str_filter(value):
    return str(value) if value else ''

# Helper function to check if user is logged in
def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_student(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'student':
            flash("Access denied. Student access required.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_manager(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'manager':
            flash("Access denied. Manager access required.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash("Access denied. Admin access required.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# HOME / LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if not email or not password:
            flash("Please fill in all fields", "error")
            return render_template("login.html")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM students WHERE email = ? AND password = ?",
            (email, password)
        )
        student = cursor.fetchone()
        
        if student:
            session['user_id'] = student['id']
            session['user_name'] = student['name']
            session['user_email'] = student['email']
            session['user_role'] = 'student'
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            session['student_email'] = student['email']
            conn.close()
            return redirect(url_for('dashboard'))
        
        cursor.execute(
            "SELECT * FROM dorm_managers WHERE email = ? AND password = ?",
            (email, password)
        )
        manager = cursor.fetchone()
        
        if manager:
            session['user_id'] = manager['id']
            session['user_name'] = manager['name']
            session['user_email'] = manager['email']
            session['user_role'] = 'manager'
            session['manager_id'] = manager['id']
            session['manager_name'] = manager['name']
            conn.close()
            return redirect(url_for('admin_dashboard'))
        
        cursor.execute(
            "SELECT * FROM admins WHERE email = ? AND password = ?",
            (email, password)
        )
        admin = cursor.fetchone()
        conn.close()
        
        if admin:
            session['user_id'] = admin['id']
            session['user_name'] = admin['name']
            session['user_email'] = admin['email']
            session['user_role'] = 'admin'
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['name']
            return redirect(url_for('super_admin_dashboard'))
        else:
            flash("Invalid email or password", "error")
    
    return render_template("login.html")

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully", "success")
    return redirect(url_for('login'))

# SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        student_id = request.form.get("student_id")
        email = request.form.get("email")
        password = request.form.get("password")
        faculty = request.form.get("faculty")
        major = request.form.get("major")
        
        if not all([name, student_id, email, password]):
            flash("All required fields must be filled", "error")
            return render_template("signup.html")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check for duplicate student ID
            cursor.execute("SELECT id FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone():
                conn.close()
                flash("Student ID already exists. Please use a different Student ID.", "error")
                return render_template("signup.html")
            
            # Check for duplicate email
            cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                flash("Email already exists. Please use a different email address.", "error")
                return render_template("signup.html")
            
            # Insert new student
            cursor.execute(
                "INSERT INTO students (student_id, name, email, password, faculty, major) VALUES (?, ?, ?, ?, ?, ?)",
                (student_id, name, email, password, faculty, major)
            )
            conn.commit()
            conn.close()
            
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            error_msg = str(e)
            if "UNIQUE constraint failed: students.student_id" in error_msg:
                flash("Student ID already exists. Please use a different Student ID.", "error")
            elif "UNIQUE constraint failed: students.email" in error_msg:
                flash("Email already exists. Please use a different email address.", "error")
            else:
                flash("This student ID or email is already registered. Please use different credentials.", "error")
        except sqlite3.OperationalError as e:
            flash("Database error. Please contact support if the problem persists.", "error")
            print(f"Database error: {e}")  # Log for debugging
        except Exception as e:
            flash(f"Error creating account: {str(e)}", "error")
            print(f"Unexpected error: {e}")  # Log for debugging
    
    return render_template("signup.html")

# DASHBOARD
@app.route("/dashboard")
@require_login
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get student's active bookings count
    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE student_id = ? AND booking_status = 'confirmed'",
        (session['student_id'],)
    )
    active_bookings = cursor.fetchone()[0]
    
    # Get pending bills count
    cursor.execute(
        "SELECT COUNT(*) FROM bills WHERE student_id = ?",
        (session['student_id'],)
    )
    pending_bills = cursor.fetchone()[0]
    
    # Get pending parcels count
    cursor.execute(
        "SELECT COUNT(*) FROM parcels WHERE student_id = ? AND status != 'picked_up'",
        (session['student_id'],)
    )
    pending_parcels = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template("dashboard.html", 
                         active_bookings=active_bookings,
                         pending_bills=pending_bills,
                         pending_parcels=pending_parcels)

# SEARCH HOSTEL
@app.route("/search", methods=["GET", "POST"])
@require_login
def search_hostel():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        location = request.form.get("location", "")
        max_price = request.form.get("max_price", "")
        room_type = request.form.get("room_type", "")
        min_rating = request.form.get("min_rating", "")
        
        query = "SELECT DISTINCT h.* FROM hostels h"
        conditions = []
        params = []
        
        if location:
            conditions.append("h.location LIKE ?")
            params.append(f"%{location}%")
        
        if max_price:
            query += " JOIN rooms r ON r.hostel_id = h.id"
            conditions.append("r.price <= ?")
            params.append(float(max_price))
        
        if room_type:
            if "JOIN rooms" not in query:
                query += " JOIN rooms r ON r.hostel_id = h.id"
            conditions.append("r.room_type = ?")
            params.append(room_type)
        
        if min_rating:
            conditions.append("h.rating >= ?")
            params.append(float(min_rating))
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(query, params)
        hostels = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM hostels")
        hostels = cursor.fetchall()
    
    conn.close()
    return render_template("search_hostel.html", hostels=hostels)

# VIEW HOSTEL DETAILS
@app.route("/hostel/<int:hostel_id>")
@require_login
def hostel_details(hostel_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM hostels WHERE id = ?", (hostel_id,))
    hostel = cursor.fetchone()
    
    if not hostel:
        flash("Hostel not found", "error")
        return redirect(url_for('search_hostel'))
    
    cursor.execute(
        "SELECT * FROM rooms WHERE hostel_id = ? AND available = 1",
        (hostel_id,)
    )
    rooms = cursor.fetchall()
    
    conn.close()
    return render_template("hostel_details.html", hostel=hostel, rooms=rooms)

# VIEW ROOM DETAILS
@app.route("/room/<int:room_id>")
@require_login
def room_details(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT r.*, h.name as hostel_name, h.location, h.rating 
           FROM rooms r 
           JOIN hostels h ON r.hostel_id = h.id 
           WHERE r.id = ?""",
        (room_id,)
    )
    room = cursor.fetchone()
    
    if not room:
        flash("Room not found", "error")
        return redirect(url_for('search_hostel'))
    
    conn.close()
    return render_template("room_details.html", room=room)

# BOOK ROOM
@app.route("/booking/<int:room_id>", methods=["GET", "POST"])
@require_login
def booking(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT r.*, h.name as hostel_name, h.location 
           FROM rooms r 
           JOIN hostels h ON r.hostel_id = h.id 
           WHERE r.id = ? AND r.available = 1""",
        (room_id,)
    )
    room = cursor.fetchone()
    
    if not room:
        flash("Room is not available", "error")
        return redirect(url_for('search_hostel'))
    
    if request.method == "POST":
        checkin_date = request.form.get("checkin_date")
        
        if not checkin_date:
            flash("Please select a check-in date", "error")
            return render_template("booking.html", room=room)
        
        today = date.today().isoformat()
        if checkin_date < today:
            flash("Cannot book rooms for past dates", "error")
            return render_template("booking.html", room=room)
        
        try:
            # Create booking
            cursor.execute(
                "INSERT INTO bookings (student_id, room_id, checkin_date, booking_status) VALUES (?, ?, ?, ?)",
                (session['student_id'], room_id, checkin_date, 'awaiting_payment')
            )
            booking_id = cursor.lastrowid
            
            # Mark room as unavailable
            cursor.execute("UPDATE rooms SET available = 0 WHERE id = ?", (room_id,))
            
            conn.commit()
            conn.close()
            
            return redirect(url_for('payment', booking_id=booking_id))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash("Error creating booking. Please try again.", "error")
    
    conn.close()
    return render_template("booking.html", room=room)

# PAYMENT
@app.route("/payment/<int:booking_id>", methods=["GET", "POST"])
@require_login
def payment(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT b.*, r.price, r.room_type, h.name as hostel_name 
           FROM bookings b 
           JOIN rooms r ON b.room_id = r.id 
           JOIN hostels h ON r.hostel_id = h.id 
           WHERE b.id = ? AND b.student_id = ?""",
        (booking_id, session['student_id'])
    )
    booking = cursor.fetchone()

    if not booking:
        flash("Booking not found", "error")
        return redirect(url_for('dashboard'))

    # Generate PromptPay QR (amount + booking reference)
    try:
        promptpay_qr_data = generate_promptpay_qr_base64(
            PROMPTPAY_ID,
            float(booking["price"]),
            reference=str(booking_id),
        )
    except Exception:
        promptpay_qr_data = None
    
    if request.method == "POST":
        payment_method = request.form.get("payment_method")
        
        if not payment_method:
            flash("Please select a payment method", "error")
            return render_template("payment.html", booking=booking, promptpay_qr_data=promptpay_qr_data)
        
        try:
            # Create payment
            cursor.execute(
                "INSERT INTO payments (booking_id, amount, payment_method, payment_status) VALUES (?, ?, ?, ?)",
                (booking_id, booking['price'], payment_method, 'completed')
            )

            # Create initial rent bill for this booking
            cursor.execute(
                "INSERT INTO bills (student_id, type, amount, due_date, status) VALUES (?, ?, ?, ?, ?)",
                (
                    session['student_id'],
                    "Monthly Rent",
                    booking['price'],
                    date.today().isoformat(),
                    "pending",
                ),
            )
            
            # After successful payment, mark booking as pending manager approval
            cursor.execute(
                "UPDATE bookings SET booking_status = 'pending' WHERE id = ?",
                (booking_id,)
            )
            
            conn.commit()
            conn.close()
            
            return redirect(url_for('confirmation', booking_id=booking_id))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash("Payment failed. Please try again.", "error")
    
    conn.close()
    return render_template("payment.html", booking=booking, promptpay_qr_data=promptpay_qr_data)

# BOOKING CONFIRMATION
@app.route("/confirmation/<int:booking_id>")
@require_login
def confirmation(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT b.*, r.room_type, r.price, h.name as hostel_name, h.location,
                  s.name as student_name, s.email
           FROM bookings b 
           JOIN rooms r ON b.room_id = r.id 
           JOIN hostels h ON r.hostel_id = h.id 
           JOIN students s ON b.student_id = s.id
           WHERE b.id = ? AND b.student_id = ?""",
        (booking_id, session['student_id'])
    )
    booking = cursor.fetchone()
    
    if not booking:
        flash("Booking not found", "error")
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template("confirmation.html", booking=booking)

# MY UNIT
@app.route("/myunit")
@require_login
def my_unit():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT b.*, r.room_type, r.price, h.name as hostel_name, h.location, h.rating
           FROM bookings b 
           JOIN rooms r ON b.room_id = r.id 
           JOIN hostels h ON r.hostel_id = h.id 
           WHERE b.student_id = ?
             AND b.booking_status IN ('pending', 'confirmed')
           ORDER BY b.checkin_date DESC""",
        (session['student_id'],)
    )
    bookings = cursor.fetchall()
    
    conn.close()
    return render_template("my_unit.html", bookings=bookings)

# PAY BILLS
@app.route("/bills", methods=["GET", "POST"])
@require_login
def bills():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        bill_id = request.form.get("bill_id")
        if bill_id:
            cursor.execute(
                "UPDATE bills SET status = 'paid' WHERE id = ? AND student_id = ?",
                (bill_id, session['student_id'])
            )
            conn.commit()
            flash("Bill paid successfully", "success")
    
    cursor.execute(
        "SELECT * FROM bills WHERE student_id = ? ORDER BY due_date ASC",
        (session['student_id'],)
    )
    bills = cursor.fetchall()
    
    conn.close()
    today = date.today().isoformat()
    return render_template("bills.html", bills=bills, today=today)

# TRACK PARCELS
@app.route("/parcels")
@require_login
def parcels():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM parcels WHERE student_id = ? ORDER BY arrival_date DESC",
        (session['student_id'],)
    )
    parcels = cursor.fetchall()
    
    conn.close()
    return render_template("parcels.html", parcels=parcels)

# Helper: student's confirmed room bookings (for facility/visitor linking)
def _get_room_bookings(cursor):
    cursor.execute(
        """SELECT b.id, b.checkin_date, r.room_type, h.name as hostel_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN hostels h ON r.hostel_id = h.id
           WHERE b.student_id = ? AND b.booking_status = 'confirmed'
           ORDER BY b.checkin_date DESC""",
        (session['student_id'],)
    )
    return cursor.fetchall()

# BOOK FACILITIES
@app.route("/facility", methods=["GET", "POST"])
@require_login
def facility_booking():
    conn = get_db_connection()
    cursor = conn.cursor()
    room_bookings = _get_room_bookings(cursor)

    if request.method == "POST":
        facility_booking_id = request.form.get("facility_booking_id")
        room_booking_id = request.form.get("room_booking_id")
        facility_name = request.form.get("facility_name")
        booking_date = request.form.get("booking_date")
        action = request.form.get("action")

        if action == "delete":
            try:
                cursor.execute(
                    "DELETE FROM facility_bookings WHERE id = ? AND student_id = ?",
                    (facility_booking_id, session['student_id'])
                )
                conn.commit()
                flash("Facility booking deleted successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error deleting booking. Please try again.", "error")
        elif action == "edit":
            if not facility_name or not booking_date or not room_booking_id:
                flash("Please fill in all fields", "error")
            else:
                today = date.today().isoformat()
                if booking_date < today:
                    flash("Cannot book facilities for past dates", "error")
                else:
                    try:
                        # Prevent duplicate facility bookings on the same date for the same stay
                        cursor.execute(
                            """
                            SELECT COUNT(*) FROM facility_bookings
                            WHERE student_id = ?
                              AND booking_id = ?
                              AND facility_name = ?
                              AND booking_date = ?
                              AND id != ?
                            """,
                            (
                                session['student_id'],
                                room_booking_id,
                                facility_name,
                                booking_date,
                                facility_booking_id,
                            ),
                        )
                        if cursor.fetchone()[0] > 0:
                            flash(
                                "You already booked this facility for this stay on that date.",
                                "error",
                            )
                        else:
                            cursor.execute(
                                "UPDATE facility_bookings SET booking_id = ?, facility_name = ?, booking_date = ? WHERE id = ? AND student_id = ?",
                                (
                                    room_booking_id,
                                    facility_name,
                                    booking_date,
                                    facility_booking_id,
                                    session['student_id'],
                                ),
                            )
                            conn.commit()
                            flash("Facility booking updated successfully", "success")
                    except Exception as e:
                        conn.rollback()
                        flash("Error updating booking. Please try again.", "error")
        else:
            if not facility_name or not booking_date or not room_booking_id:
                flash("Please fill in all fields including Your stay", "error")
                cursor.execute(
                    """SELECT fb.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
                       FROM facility_bookings fb
                       JOIN bookings b ON fb.booking_id = b.id
                       JOIN rooms r ON b.room_id = r.id
                       JOIN hostels h ON r.hostel_id = h.id
                       WHERE fb.student_id = ? ORDER BY fb.booking_date DESC""",
                    (session['student_id'],)
                )
                bookings = cursor.fetchall()
                conn.close()
                return render_template("facility_booking.html", bookings=bookings, room_bookings=room_bookings)
            today = date.today().isoformat()
            if booking_date < today:
                flash("Cannot book facilities for past dates", "error")
                cursor.execute(
                    """SELECT fb.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
                       FROM facility_bookings fb
                       JOIN bookings b ON fb.booking_id = b.id
                       JOIN rooms r ON b.room_id = r.id
                       JOIN hostels h ON r.hostel_id = h.id
                       WHERE fb.student_id = ? ORDER BY fb.booking_date DESC""",
                    (session['student_id'],)
                )
                bookings = cursor.fetchall()
                conn.close()
                return render_template("facility_booking.html", bookings=bookings, room_bookings=room_bookings)
            try:
                cursor.execute(
                    "SELECT id FROM bookings WHERE id = ? AND student_id = ? AND booking_status = 'confirmed'",
                    (room_booking_id, session['student_id'])
                )
                if not cursor.fetchone():
                    flash("Invalid room booking selected.", "error")
                else:
                    # Prevent duplicate facility bookings on the same date for the same stay
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM facility_bookings
                        WHERE student_id = ?
                          AND booking_id = ?
                          AND facility_name = ?
                          AND booking_date = ?
                        """,
                        (session['student_id'], room_booking_id, facility_name, booking_date),
                    )
                    if cursor.fetchone()[0] > 0:
                        flash(
                            "You already booked this facility for this stay on that date.",
                            "error",
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO facility_bookings (student_id, booking_id, facility_name, booking_date) VALUES (?, ?, ?, ?)",
                            (session['student_id'], room_booking_id, facility_name, booking_date)
                        )
                        conn.commit()
                        flash("Facility booked successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error booking facility. Please try again.", "error")

    cursor.execute(
        """SELECT fb.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
           FROM facility_bookings fb
           JOIN bookings b ON fb.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN hostels h ON r.hostel_id = h.id
           WHERE fb.student_id = ? ORDER BY fb.booking_date DESC""",
        (session['student_id'],)
    )
    bookings = cursor.fetchall()
    conn.close()
    return render_template("facility_booking.html", bookings=bookings, room_bookings=room_bookings)

# EDIT FACILITY BOOKING
@app.route("/facility/edit/<int:facility_booking_id>")
@require_login
def edit_facility_booking(facility_booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    room_bookings = _get_room_bookings(cursor)
    cursor.execute(
        "SELECT * FROM facility_bookings WHERE id = ? AND student_id = ?",
        (facility_booking_id, session['student_id'])
    )
    booking = cursor.fetchone()
    if not booking:
        flash("Booking not found", "error")
        conn.close()
        return redirect(url_for('facility_booking'))
    cursor.execute(
        """SELECT fb.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
           FROM facility_bookings fb
           JOIN bookings b ON fb.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN hostels h ON r.hostel_id = h.id
           WHERE fb.student_id = ? ORDER BY fb.booking_date DESC""",
        (session['student_id'],)
    )
    bookings = cursor.fetchall()
    conn.close()
    return render_template("facility_booking.html", bookings=bookings, room_bookings=room_bookings, editing_booking=booking)

# SUBMIT REPAIR REQUEST
@app.route("/repair", methods=["GET", "POST"])
@require_login
def repair_request():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        request_id = request.form.get("request_id")
        issue_type = request.form.get("issue_type")
        description = request.form.get("description")
        action = request.form.get("action")
        
        if action == "delete":
            try:
                cursor.execute(
                    "DELETE FROM repair_requests WHERE id = ? AND student_id = ?",
                    (request_id, session['student_id'])
                )
                conn.commit()
                flash("Repair request deleted successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error deleting request. Please try again.", "error")
        elif action == "edit":
            if not issue_type or not description:
                flash("Please fill in all fields", "error")
            else:
                try:
                    cursor.execute(
                        "UPDATE repair_requests SET issue_type = ?, description = ? WHERE id = ? AND student_id = ?",
                        (issue_type, description, request_id, session['student_id'])
                    )
                    conn.commit()
                    flash("Repair request updated successfully", "success")
                except Exception as e:
                    conn.rollback()
                    flash("Error updating request. Please try again.", "error")
        else:
            if not issue_type or not description:
                flash("Please fill in all fields", "error")
                cursor.execute(
                    "SELECT * FROM repair_requests WHERE student_id = ? ORDER BY report_date DESC",
                    (session['student_id'],)
                )
                requests = cursor.fetchall()
                conn.close()
                return render_template("repair_request.html", requests=requests)
            
            try:
                cursor.execute(
                    "INSERT INTO repair_requests (student_id, issue_type, description, status, report_date) VALUES (?, ?, ?, ?, ?)",
                    (session['student_id'], issue_type, description, 'pending', datetime.now().strftime('%Y-%m-%d'))
                )
                conn.commit()
                flash("Repair request submitted successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error submitting request. Please try again.", "error")
    
    cursor.execute(
        "SELECT * FROM repair_requests WHERE student_id = ? ORDER BY report_date DESC",
        (session['student_id'],)
    )
    requests = cursor.fetchall()
    
    conn.close()
    return render_template("repair_request.html", requests=requests)

# EDIT REPAIR REQUEST
@app.route("/repair/edit/<int:request_id>")
@require_login
def edit_repair_request(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM repair_requests WHERE id = ? AND student_id = ?",
        (request_id, session['student_id'])
    )
    request = cursor.fetchone()
    
    if not request:
        flash("Repair request not found", "error")
        conn.close()
        return redirect('/repair')
    
    cursor.execute(
        "SELECT * FROM repair_requests WHERE student_id = ? ORDER BY report_date DESC",
        (session['student_id'],)
    )
    requests = cursor.fetchall()
    
    conn.close()
    return render_template("repair_request.html", requests=requests, editing_request=request)

# REGISTER VISITOR
@app.route("/visitor", methods=["GET", "POST"])
@require_login
def visitor():
    conn = get_db_connection()
    cursor = conn.cursor()
    room_bookings = _get_room_bookings(cursor)

    if request.method == "POST":
        visitor_id = request.form.get("visitor_id")
        room_booking_id = request.form.get("room_booking_id")
        visitor_name = request.form.get("visitor_name")
        visit_date = request.form.get("visit_date")
        visit_time = request.form.get("visit_time")
        action = request.form.get("action")

        if action == "delete":
            try:
                cursor.execute(
                    "DELETE FROM visitors WHERE id = ? AND student_id = ?",
                    (visitor_id, session['student_id'])
                )
                conn.commit()
                flash("Visitor registration deleted successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error deleting visitor. Please try again.", "error")
        elif action == "edit":
            if not all([visitor_name, visit_date, visit_time, room_booking_id]):
                flash("Please fill in all fields", "error")
            else:
                try:
                    visit_datetime = datetime.strptime(f"{visit_date} {visit_time}", "%Y-%m-%d %H:%M")
                    if visit_datetime < datetime.now():
                        flash("Cannot register visitors for past date/time", "error")
                    else:
                        cursor.execute(
                            "UPDATE visitors SET booking_id = ?, visitor_name = ?, visit_date = ?, visit_time = ? WHERE id = ? AND student_id = ?",
                            (room_booking_id, visitor_name, visit_date, visit_time, visitor_id, session['student_id'])
                        )
                        conn.commit()
                        flash("Visitor registration updated successfully", "success")
                except ValueError:
                    flash("Invalid date or time format", "error")
                except Exception as e:
                    conn.rollback()
                    flash("Error updating visitor. Please try again.", "error")
        else:
            if not all([visitor_name, visit_date, visit_time, room_booking_id]):
                flash("Please fill in all fields including Your stay", "error")
                cursor.execute(
                    """SELECT v.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
                       FROM visitors v
                       JOIN bookings b ON v.booking_id = b.id
                       JOIN rooms r ON b.room_id = r.id
                       JOIN hostels h ON r.hostel_id = h.id
                       WHERE v.student_id = ? ORDER BY v.visit_date DESC""",
                    (session['student_id'],)
                )
                visitors = cursor.fetchall()
                conn.close()
                return render_template("visitor.html", visitors=visitors, room_bookings=room_bookings)
            try:
                visit_datetime = datetime.strptime(f"{visit_date} {visit_time}", "%Y-%m-%d %H:%M")
                if visit_datetime < datetime.now():
                    flash("Cannot register visitors for past date/time", "error")
                    cursor.execute(
                        """SELECT v.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
                           FROM visitors v
                           JOIN bookings b ON v.booking_id = b.id
                           JOIN rooms r ON b.room_id = r.id
                           JOIN hostels h ON r.hostel_id = h.id
                           WHERE v.student_id = ? ORDER BY v.visit_date DESC""",
                        (session['student_id'],)
                    )
                    visitors = cursor.fetchall()
                    conn.close()
                    return render_template("visitor.html", visitors=visitors, room_bookings=room_bookings)
                cursor.execute(
                    "SELECT id FROM bookings WHERE id = ? AND student_id = ? AND booking_status = 'confirmed'",
                    (room_booking_id, session['student_id'])
                )
                if not cursor.fetchone():
                    flash("Invalid room booking selected.", "error")
                else:
                    cursor.execute(
                        "INSERT INTO visitors (student_id, booking_id, visitor_name, visit_date, visit_time) VALUES (?, ?, ?, ?, ?)",
                        (session['student_id'], room_booking_id, visitor_name, visit_date, visit_time)
                    )
                    conn.commit()
                    flash("Visitor registered successfully", "success")
            except ValueError:
                flash("Invalid date or time format", "error")
                cursor.execute(
                    """SELECT v.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
                       FROM visitors v
                       JOIN bookings b ON v.booking_id = b.id
                       JOIN rooms r ON b.room_id = r.id
                       JOIN hostels h ON r.hostel_id = h.id
                       WHERE v.student_id = ? ORDER BY v.visit_date DESC""",
                    (session['student_id'],)
                )
                visitors = cursor.fetchall()
                conn.close()
                return render_template("visitor.html", visitors=visitors, room_bookings=room_bookings)
            except Exception as e:
                conn.rollback()
                flash("Error registering visitor. Please try again.", "error")

    cursor.execute(
        """SELECT v.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
           FROM visitors v
           JOIN bookings b ON v.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN hostels h ON r.hostel_id = h.id
           WHERE v.student_id = ? ORDER BY v.visit_date DESC""",
        (session['student_id'],)
    )
    visitors = cursor.fetchall()
    conn.close()
    return render_template("visitor.html", visitors=visitors, room_bookings=room_bookings)

# EDIT VISITOR
@app.route("/visitor/edit/<int:visitor_id>")
@require_login
def edit_visitor(visitor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    room_bookings = _get_room_bookings(cursor)
    cursor.execute(
        "SELECT * FROM visitors WHERE id = ? AND student_id = ?",
        (visitor_id, session['student_id'])
    )
    visitor = cursor.fetchone()
    if not visitor:
        flash("Visitor not found", "error")
        conn.close()
        return redirect(url_for('visitor'))
    cursor.execute(
        """SELECT v.*, b.checkin_date as room_checkin, r.room_type, h.name as hostel_name
           FROM visitors v
           JOIN bookings b ON v.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN hostels h ON r.hostel_id = h.id
           WHERE v.student_id = ? ORDER BY v.visit_date DESC""",
        (session['student_id'],)
    )
    visitors = cursor.fetchall()
    conn.close()
    return render_template("visitor.html", visitors=visitors, room_bookings=room_bookings, editing_visitor=visitor)

# SEND SUGGESTION
@app.route("/suggestion", methods=["GET", "POST"])
@require_login
def suggestion():
    if request.method == "POST":
        suggestion_text = request.form.get("suggestion")
        
        if not suggestion_text:
            flash("Please enter your suggestion", "error")
            return render_template("suggestion.html")
        
        # In a real app, you would save this to a suggestions table
        flash("Thank you for your suggestion!", "success")
        return redirect(url_for('dashboard'))
    
    return render_template("suggestion.html")

# CHAT WITH DORM MANAGER
@app.route("/chat", methods=["GET", "POST"])
@require_student
def chat():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        message = request.form.get("message")
        
        if message:
            try:
                cursor.execute(
                    "INSERT INTO chat_messages (student_id, message, sender, timestamp) VALUES (?, ?, ?, ?)",
                    (session['student_id'], message, 'student', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                conn.commit()
                flash("Message sent to dorm manager", "success")
            except Exception as e:
                conn.rollback()
                flash("Error sending message. Please try again.", "error")
    
    cursor.execute(
        "SELECT * FROM chat_messages WHERE student_id = ? ORDER BY timestamp ASC",
        (session['student_id'],)
    )
    messages = cursor.fetchall()
    
    conn.close()
    return render_template("chat.html", messages=messages)

# VIEW COMMUNITY RULES
@app.route("/rules")
@require_login
def rules():
    return render_template("rules.html")

# ADMIN DASHBOARD
@app.route("/admin/dashboard")
@require_manager
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'pending'")
    pending_applications = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'confirmed'")
    confirmed_bookings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM repair_requests WHERE status = 'pending'")
    pending_repairs = cursor.fetchone()[0]
    
    try:
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE sender = 'student'")
        unread_messages = cursor.fetchone()[0]
    except:
        unread_messages = 0
    
    conn.close()
    return render_template("admin_dashboard.html",
                         pending_applications=pending_applications,
                         confirmed_bookings=confirmed_bookings,
                         pending_repairs=pending_repairs,
                         unread_messages=unread_messages)

# VIEW STUDENT APPLICATIONS
@app.route("/admin/applications")
@require_manager
def view_applications():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT b.*, s.name as student_name, s.email as student_email, s.student_id,
               r.room_type, r.price, h.name as hostel_name, h.location
        FROM bookings b
        JOIN students s ON b.student_id = s.id
        JOIN rooms r ON b.room_id = r.id
        JOIN hostels h ON r.hostel_id = h.id
        ORDER BY 
            CASE 
                WHEN b.booking_status = 'pending' THEN 0
                WHEN b.booking_status = 'awaiting_payment' THEN 1
                WHEN b.booking_status = 'confirmed' THEN 2
                WHEN b.booking_status = 'rejected' THEN 3
                ELSE 4
            END,
            b.id DESC
    """)
    applications = cursor.fetchall()
    
    conn.close()
    return render_template("admin_applications.html", applications=applications)

# APPROVE/REJECT APPLICATION
@app.route("/admin/application/<int:booking_id>/<action>", methods=["POST"])
@require_manager
def manage_application(booking_id, action):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if action == "approve":
        try:
            cursor.execute(
                "UPDATE bookings SET booking_status = 'confirmed' WHERE id = ?",
                (booking_id,)
            )
            conn.commit()
            flash("Application approved successfully", "success")
        except Exception as e:
            conn.rollback()
            flash("Error approving application. Please try again.", "error")
    elif action == "reject":
        try:
            cursor.execute(
                "UPDATE bookings SET booking_status = 'rejected' WHERE id = ?",
                (booking_id,)
            )
            cursor.execute(
                "UPDATE rooms SET available = 1 WHERE id = (SELECT room_id FROM bookings WHERE id = ?)",
                (booking_id,)
            )
            conn.commit()
            flash("Application rejected successfully", "success")
        except Exception as e:
            conn.rollback()
            flash("Error rejecting application. Please try again.", "error")
    
    conn.close()
    return redirect(url_for('view_applications'))

# MANAGE ROOMS
@app.route("/admin/rooms")
@require_manager
def manage_rooms():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.*, h.name as hostel_name, h.location
        FROM rooms r
        JOIN hostels h ON r.hostel_id = h.id
        ORDER BY h.name, r.room_type
    """)
    rooms = cursor.fetchall()
    
    conn.close()
    return render_template("admin_rooms.html", rooms=rooms)


@app.route("/admin/rooms/new")
@require_manager
def new_room():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hostels ORDER BY name")
    hostels = cursor.fetchall()
    conn.close()
    return render_template(
        "admin_room_form.html",
        room=None,
        hostels=hostels,
        form_action=url_for("save_room"),
    )


@app.route("/admin/rooms/<int:room_id>/edit")
@require_manager
def edit_room(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, h.name as hostel_name, h.location
        FROM rooms r
        JOIN hostels h ON r.hostel_id = h.id
        WHERE r.id = ?
    """, (room_id,))
    room = cursor.fetchone()
    cursor.execute("SELECT * FROM hostels ORDER BY name")
    hostels = cursor.fetchall()
    conn.close()
    if not room:
        flash("Room not found", "error")
        return redirect(url_for("manage_rooms"))
    return render_template(
        "admin_room_form.html",
        room=room,
        hostels=hostels,
        form_action=url_for("save_room", room_id=room_id),
    )

# ADD/EDIT ROOM
@app.route("/admin/room", methods=["POST"])
@app.route("/admin/room/<int:room_id>", methods=["POST"])
@require_manager
def save_room(room_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    hostel_id = request.form.get("hostel_id")
    room_type = request.form.get("room_type")
    price = request.form.get("price")
    facilities = request.form.get("facilities", "")
    available = request.form.get("available", "1")
    
    if not all([hostel_id, room_type, price]):
        flash("Please fill in all required fields", "error")
        conn.close()
        return redirect(url_for('manage_rooms'))
    
    try:
        if room_id:
            cursor.execute(
                "UPDATE rooms SET hostel_id = ?, room_type = ?, price = ?, facilities = ?, available = ? WHERE id = ?",
                (hostel_id, room_type, float(price), facilities, int(available), room_id)
            )
            flash("Room updated successfully", "success")
        else:
            cursor.execute(
                "INSERT INTO rooms (hostel_id, room_type, price, facilities, available) VALUES (?, ?, ?, ?, ?)",
                (hostel_id, room_type, float(price), facilities, int(available))
            )
            flash("Room added successfully", "success")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash("Error saving room. Please try again.", "error")
    finally:
        conn.close()
    
    return redirect(url_for('manage_rooms'))

# DELETE ROOM
@app.route("/admin/room/<int:room_id>/delete", methods=["POST"])
@require_manager
def delete_room(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        conn.commit()
        flash("Room deleted successfully", "success")
    except Exception as e:
        conn.rollback()
        flash("Error deleting room. Please try again.", "error")
    finally:
        conn.close()
    
    return redirect(url_for('manage_rooms'))

# VIEW REPAIR REQUESTS
@app.route("/admin/repairs")
@require_manager
def view_repairs():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.*, s.name as student_name, s.student_id, s.email as student_email
        FROM repair_requests r
        JOIN students s ON r.student_id = s.id
        ORDER BY r.report_date DESC, r.status
    """)
    repairs = cursor.fetchall()
    
    conn.close()
    return render_template("admin_repairs.html", repairs=repairs)

# UPDATE REPAIR STATUS
@app.route("/admin/repair/<int:repair_id>/update", methods=["POST"])
@require_manager
def update_repair(repair_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status = request.form.get("status")
    
    if status not in ['pending', 'in_progress', 'completed']:
        flash("Invalid status", "error")
        conn.close()
        return redirect(url_for('view_repairs'))
    
    try:
        cursor.execute(
            "UPDATE repair_requests SET status = ? WHERE id = ?",
            (status, repair_id)
        )
        conn.commit()
        flash("Repair request updated successfully", "success")
    except Exception as e:
        conn.rollback()
        flash("Error updating repair request. Please try again.", "error")
    finally:
        conn.close()
    
    return redirect(url_for('view_repairs'))

# MANAGER CHAT - LIST CHAT ROOMS
@app.route("/admin/chat")
@require_manager
def manager_chat():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT cm.student_id, s.name, s.student_id as student_id_text, s.email,
               (SELECT message FROM chat_messages WHERE student_id = cm.student_id ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM chat_messages WHERE student_id = cm.student_id ORDER BY timestamp DESC LIMIT 1) as last_timestamp
        FROM chat_messages cm
        JOIN students s ON cm.student_id = s.id
        ORDER BY last_timestamp DESC
    """)
    chat_rooms = cursor.fetchall()
    
    conn.close()
    return render_template("admin_chat.html", chat_rooms=chat_rooms)

# MANAGER CHAT - VIEW CONVERSATION
@app.route("/admin/chat/<int:student_id>", methods=["GET", "POST"])
@require_manager
def manager_chat_conversation(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        message = request.form.get("message")
        
        if message:
            try:
                cursor.execute(
                    "INSERT INTO chat_messages (student_id, message, sender, timestamp) VALUES (?, ?, ?, ?)",
                    (student_id, message, 'manager', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                conn.commit()
                flash("Message sent successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error sending message. Please try again.", "error")
    
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    
    if not student:
        flash("Student not found", "error")
        conn.close()
        return redirect(url_for('manager_chat'))
    
    cursor.execute("""
        SELECT * FROM chat_messages 
        WHERE student_id = ? 
        ORDER BY timestamp ASC
    """, (student_id,))
    messages = cursor.fetchall()
    
    cursor.execute("""
        SELECT DISTINCT cm.student_id, s.name, s.student_id as student_id_text, s.email,
               (SELECT message FROM chat_messages WHERE student_id = cm.student_id ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM chat_messages WHERE student_id = cm.student_id ORDER BY timestamp DESC LIMIT 1) as last_timestamp
        FROM chat_messages cm
        JOIN students s ON cm.student_id = s.id
        ORDER BY last_timestamp DESC
    """)
    chat_rooms = cursor.fetchall()
    
    conn.close()
    return render_template("admin_chat.html", chat_rooms=chat_rooms, current_student=student, messages=messages)

# CHECK DUPLICATE STUDENT ID (AJAX endpoint)
@app.route("/check-student-id")
def check_student_id():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'exists': False})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE student_id = ?", (student_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    
    return jsonify({'exists': exists})

# CHECK DUPLICATE EMAIL (AJAX endpoint)
@app.route("/check-email")
def check_email():
    email = request.args.get('email')
    if not email:
        return jsonify({'exists': False})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
    exists = cursor.fetchone() is not None
    conn.close()
    
    return jsonify({'exists': exists})

# LIST ALL HOSTELS (for testing)
@app.route("/hostels")
def hostels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hostels")
    hostels = cursor.fetchall()
    conn.close()
    return render_template("hostels.html", hostels=hostels)

# ==================== ADMIN ROUTES ====================

# SUPER ADMIN DASHBOARD
@app.route("/super-admin/dashboard")
@require_admin
def super_admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dorm_managers")
    total_managers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM hostels")
    total_hostels = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE booking_status = 'confirmed'")
    total_bookings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'pending'")
    pending_payments = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE payment_status = 'completed'")
    total_revenue = cursor.fetchone()[0] or 0
    
    conn.close()
    return render_template("super_admin_dashboard.html",
                         total_students=total_students,
                         total_managers=total_managers,
                         total_hostels=total_hostels,
                         total_bookings=total_bookings,
                         pending_payments=pending_payments,
                         total_revenue=total_revenue)

# MANAGE USERS - VIEW ALL
@app.route("/super-admin/users")
@require_admin
def manage_users():
    user_type = request.args.get('type', 'students')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_type == 'students':
        cursor.execute("SELECT * FROM students ORDER BY id DESC")
        users = cursor.fetchall()
        user_type_name = 'Students'
    else:
        cursor.execute("SELECT * FROM dorm_managers ORDER BY id DESC")
        users = cursor.fetchall()
        user_type_name = 'Managers'
    
    conn.close()
    
    users_list = [dict(user) for user in users]
    
    return render_template("super_admin_users.html", users=users, users_json=users_list, user_type=user_type, user_type_name=user_type_name)

# MANAGE USERS - ADD/EDIT
@app.route("/super-admin/user", methods=["POST"])
@app.route("/super-admin/user/<int:user_id>", methods=["POST"])
@require_admin
def save_user(user_id=None):
    user_type = request.form.get("user_type")
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if not user_type or not name or not email:
            flash("Missing required fields", "error")
            conn.close()
            return redirect(url_for('manage_users', type=user_type or 'students'))
        
        if user_type == 'student' or user_type == 'students':
            student_id = request.form.get("student_id")
            faculty = request.form.get("faculty")
            major = request.form.get("major")
            
            if not student_id and not user_id:
                flash("Student ID is required", "error")
                conn.close()
                return redirect(url_for('manage_users', type='students'))
            
            if not password and not user_id:
                flash("Password is required for new students", "error")
                conn.close()
                return redirect(url_for('manage_users', type='students'))

            # Duplicate checks for students
            if user_id:
                cursor.execute("SELECT id FROM students WHERE email = ? AND id != ?", (email, user_id))
                if cursor.fetchone():
                    flash("Email already exists. Please use a different email address.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='students'))
                cursor.execute("SELECT id FROM students WHERE student_id = ? AND id != ?", (student_id, user_id))
                if cursor.fetchone():
                    flash("Student ID already exists. Please use a different Student ID.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='students'))
            else:
                cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
                if cursor.fetchone():
                    flash("Email already exists. Please use a different email address.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='students'))
                cursor.execute("SELECT id FROM students WHERE student_id = ?", (student_id,))
                if cursor.fetchone():
                    flash("Student ID already exists. Please use a different Student ID.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='students'))
            
            if user_id:
                if password:
                    cursor.execute(
                        "UPDATE students SET name = ?, email = ?, password = ?, faculty = ?, major = ? WHERE id = ?",
                        (name, email, password, faculty, major, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE students SET name = ?, email = ?, faculty = ?, major = ? WHERE id = ?",
                        (name, email, faculty, major, user_id)
                    )
                flash("Student updated successfully", "success")
            else:
                cursor.execute(
                    "INSERT INTO students (student_id, name, email, password, faculty, major) VALUES (?, ?, ?, ?, ?, ?)",
                    (student_id, name, email, password, faculty, major)
                )
                flash("Student added successfully", "success")
        elif user_type == 'manager' or user_type == 'managers':
            manager_id = request.form.get("manager_id")
            phone_number = request.form.get("phone_number")
            line_id = request.form.get("line_id")
            
            if not manager_id and not user_id:
                flash("Manager ID is required", "error")
                conn.close()
                return redirect(url_for('manage_users', type='managers'))
            
            if not password and not user_id:
                flash("Password is required for new managers", "error")
                conn.close()
                return redirect(url_for('manage_users', type='managers'))

            # Duplicate checks for managers
            if user_id:
                cursor.execute("SELECT id FROM dorm_managers WHERE email = ? AND id != ?", (email, user_id))
                if cursor.fetchone():
                    flash("Email already exists. Please use a different email address.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='managers'))
                cursor.execute("SELECT id FROM dorm_managers WHERE manager_id = ? AND id != ?", (manager_id, user_id))
                if cursor.fetchone():
                    flash("Manager ID already exists. Please use a different Manager ID.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='managers'))
            else:
                cursor.execute("SELECT id FROM dorm_managers WHERE email = ?", (email,))
                if cursor.fetchone():
                    flash("Email already exists. Please use a different email address.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='managers'))
                cursor.execute("SELECT id FROM dorm_managers WHERE manager_id = ?", (manager_id,))
                if cursor.fetchone():
                    flash("Manager ID already exists. Please use a different Manager ID.", "error")
                    conn.close()
                    return redirect(url_for('manage_users', type='managers'))
            
            if user_id:
                if password:
                    cursor.execute(
                        "UPDATE dorm_managers SET name = ?, email = ?, password = ?, phone_number = ?, line_id = ? WHERE id = ?",
                        (name, email, password, phone_number, line_id, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE dorm_managers SET name = ?, email = ?, phone_number = ?, line_id = ? WHERE id = ?",
                        (name, email, phone_number, line_id, user_id)
                    )
                flash("Manager updated successfully", "success")
            else:
                cursor.execute(
                    "INSERT INTO dorm_managers (manager_id, name, email, password, phone_number, line_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (manager_id, name, email, password, phone_number, line_id)
                )
                flash("Manager added successfully", "success")
        else:
            flash("Invalid user type", "error")
            conn.close()
            return redirect(url_for('manage_users', type='students'))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error saving user: {str(e)}", "error")
    finally:
        conn.close()
    
    redirect_type = 'students' if (user_type == 'student' or user_type == 'students') else 'managers'
    return redirect(url_for('manage_users', type=redirect_type))

# MANAGE USERS - DELETE
@app.route("/super-admin/user/<int:user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    user_type = request.form.get("user_type")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if user_type == 'student':
            cursor.execute("DELETE FROM students WHERE id = ?", (user_id,))
            flash("Student deleted successfully", "success")
        else:
            cursor.execute("DELETE FROM dorm_managers WHERE id = ?", (user_id,))
            flash("Manager deleted successfully", "success")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting user: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for('manage_users', type=user_type))

# MANAGE HOSTELS - VIEW ALL
@app.route("/super-admin/hostels")
@require_admin
def manage_hostels():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM hostels ORDER BY name")
    hostels = cursor.fetchall()
    
    conn.close()
    
    hostels_list = [dict(hostel) for hostel in hostels]
    
    return render_template("super_admin_hostels.html", hostels=hostels, hostels_json=hostels_list)

# MANAGE HOSTELS - ADD/EDIT
@app.route("/super-admin/hostel", methods=["POST"])
@app.route("/super-admin/hostel/<int:hostel_id>", methods=["POST"])
@require_admin
def save_hostel(hostel_id=None):
    name = request.form.get("name")
    location = request.form.get("location")
    distance_from_campus = request.form.get("distance_from_campus")
    rating = request.form.get("rating")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if hostel_id:
            cursor.execute(
                "UPDATE hostels SET name = ?, location = ?, distance_from_campus = ?, rating = ? WHERE id = ?",
                (name, location, float(distance_from_campus) if distance_from_campus else None, 
                 float(rating) if rating else None, hostel_id)
            )
            flash("Hostel updated successfully", "success")
        else:
            cursor.execute(
                "INSERT INTO hostels (name, location, distance_from_campus, rating) VALUES (?, ?, ?, ?)",
                (name, location, float(distance_from_campus) if distance_from_campus else None,
                 float(rating) if rating else None)
            )
            flash("Hostel added successfully", "success")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error saving hostel: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for('manage_hostels'))

# MANAGE HOSTELS - DELETE
@app.route("/super-admin/hostel/<int:hostel_id>/delete", methods=["POST"])
@require_admin
def delete_hostel(hostel_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM hostels WHERE id = ?", (hostel_id,))
        conn.commit()
        flash("Hostel deleted successfully", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting hostel: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for('manage_hostels'))

# MANAGE SYSTEM
@app.route("/super-admin/system")
@require_admin
def manage_system():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dorm_managers")
    total_managers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM admins")
    total_admins = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM hostels")
    total_hostels = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM rooms")
    total_rooms = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM bookings")
    total_bookings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM payments")
    total_payments = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM bills")
    total_bills = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM parcels")
    total_parcels = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM facility_bookings")
    total_facility_bookings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM repair_requests")
    total_repair_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM visitors")
    total_visitors = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chat_messages")
    total_chat_messages = cursor.fetchone()[0]
    
    conn.close()
    return render_template("super_admin_system.html",
                         total_students=total_students,
                         total_managers=total_managers,
                         total_admins=total_admins,
                         total_hostels=total_hostels,
                         total_rooms=total_rooms,
                         total_bookings=total_bookings,
                         total_payments=total_payments,
                         total_bills=total_bills,
                         total_parcels=total_parcels,
                         total_facility_bookings=total_facility_bookings,
                         total_repair_requests=total_repair_requests,
                         total_visitors=total_visitors,
                         total_chat_messages=total_chat_messages)

# PROCESS PAYMENT - VIEW ALL
@app.route("/super-admin/payments")
@require_admin
def process_payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, b.student_id, s.name as student_name, s.email as student_email,
               r.room_type, h.name as hostel_name, b.checkin_date
        FROM payments p
        LEFT JOIN bookings b ON p.booking_id = b.id
        LEFT JOIN students s ON b.student_id = s.id
        LEFT JOIN rooms r ON b.room_id = r.id
        LEFT JOIN hostels h ON r.hostel_id = h.id
        ORDER BY p.id DESC
    """)
    payments = cursor.fetchall()
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE payment_status = 'completed'")
    total_revenue = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE payment_status = 'pending'")
    pending_amount = cursor.fetchone()[0] or 0
    
    conn.close()
    return render_template("super_admin_payments.html", payments=payments, total_revenue=total_revenue, pending_amount=pending_amount)

# PROCESS PAYMENT - UPDATE STATUS
@app.route("/super-admin/payment/<int:payment_id>/update", methods=["POST"])
@require_admin
def update_payment_status(payment_id):
    status = request.form.get("status")
    
    if status not in ['pending', 'completed', 'failed', 'refunded']:
        flash("Invalid payment status", "error")
        return redirect(url_for('process_payments'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE payments SET payment_status = ? WHERE id = ?",
            (status, payment_id)
        )
        conn.commit()
        flash("Payment status updated successfully", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating payment status: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for('process_payments'))

if __name__ == "__main__":
    app.run(debug=True)