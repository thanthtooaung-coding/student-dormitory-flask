from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db_connection
from datetime import datetime, date
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

@app.context_processor
def inject_current_year():
    return dict(current_year=date.today().year)

@app.template_filter('date_str')
def date_str_filter(value):
    return str(value) if value else ''

# Helper function to check if user is logged in
def require_login(f):
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
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
        conn.close()
        
        if student:
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            session['student_email'] = student['email']
            return redirect(url_for('dashboard'))
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
                (session['student_id'], room_id, checkin_date, 'pending')
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
    
    if request.method == "POST":
        payment_method = request.form.get("payment_method")
        
        if not payment_method:
            flash("Please select a payment method", "error")
            return render_template("payment.html", booking=booking)
        
        try:
            # Create payment
            cursor.execute(
                "INSERT INTO payments (booking_id, amount, payment_method, payment_status) VALUES (?, ?, ?, ?)",
                (booking_id, booking['price'], payment_method, 'completed')
            )
            
            # Update booking status
            cursor.execute(
                "UPDATE bookings SET booking_status = 'confirmed' WHERE id = ?",
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
    return render_template("payment.html", booking=booking)

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
           WHERE b.student_id = ? AND b.booking_status = 'confirmed'
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

# BOOK FACILITIES
@app.route("/facility", methods=["GET", "POST"])
@require_login
def facility_booking():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        booking_id = request.form.get("booking_id")
        facility_name = request.form.get("facility_name")
        booking_date = request.form.get("booking_date")
        action = request.form.get("action")
        
        if action == "delete":
            try:
                cursor.execute(
                    "DELETE FROM facility_bookings WHERE id = ? AND student_id = ?",
                    (booking_id, session['student_id'])
                )
                conn.commit()
                flash("Facility booking deleted successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error deleting booking. Please try again.", "error")
        elif action == "edit":
            if not facility_name or not booking_date:
                flash("Please fill in all fields", "error")
            else:
                today = date.today().isoformat()
                if booking_date < today:
                    flash("Cannot book facilities for past dates", "error")
                else:
                    try:
                        cursor.execute(
                            "UPDATE facility_bookings SET facility_name = ?, booking_date = ? WHERE id = ? AND student_id = ?",
                            (facility_name, booking_date, booking_id, session['student_id'])
                        )
                        conn.commit()
                        flash("Facility booking updated successfully", "success")
                    except Exception as e:
                        conn.rollback()
                        flash("Error updating booking. Please try again.", "error")
        else:
            if not facility_name or not booking_date:
                flash("Please fill in all fields", "error")
                bookings = cursor.execute(
                    "SELECT * FROM facility_bookings WHERE student_id = ? ORDER BY booking_date DESC",
                    (session['student_id'],)
                ).fetchall()
                conn.close()
                return render_template("facility_booking.html", bookings=bookings)
            
            today = date.today().isoformat()
            if booking_date < today:
                flash("Cannot book facilities for past dates", "error")
                bookings = cursor.execute(
                    "SELECT * FROM facility_bookings WHERE student_id = ? ORDER BY booking_date DESC",
                    (session['student_id'],)
                ).fetchall()
                conn.close()
                return render_template("facility_booking.html", bookings=bookings)
            
            try:
                cursor.execute(
                    "INSERT INTO facility_bookings (student_id, facility_name, booking_date) VALUES (?, ?, ?)",
                    (session['student_id'], facility_name, booking_date)
                )
                conn.commit()
                flash("Facility booked successfully", "success")
            except Exception as e:
                conn.rollback()
                flash("Error booking facility. Please try again.", "error")
    
    cursor.execute(
        "SELECT * FROM facility_bookings WHERE student_id = ? ORDER BY booking_date DESC",
        (session['student_id'],)
    )
    bookings = cursor.fetchall()
    
    conn.close()
    return render_template("facility_booking.html", bookings=bookings)

# EDIT FACILITY BOOKING
@app.route("/facility/edit/<int:booking_id>")
@require_login
def edit_facility_booking(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM facility_bookings WHERE id = ? AND student_id = ?",
        (booking_id, session['student_id'])
    )
    booking = cursor.fetchone()
    
    if not booking:
        flash("Booking not found", "error")
        conn.close()
        return redirect(url_for('facility_booking'))
    
    cursor.execute(
        "SELECT * FROM facility_bookings WHERE student_id = ? ORDER BY booking_date DESC",
        (session['student_id'],)
    )
    bookings = cursor.fetchall()
    
    conn.close()
    return render_template("facility_booking.html", bookings=bookings, editing_booking=booking)

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
    
    if request.method == "POST":
        visitor_id = request.form.get("visitor_id")
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
            if not all([visitor_name, visit_date, visit_time]):
                flash("Please fill in all fields", "error")
            else:
                try:
                    visit_datetime = datetime.strptime(f"{visit_date} {visit_time}", "%Y-%m-%d %H:%M")
                    if visit_datetime < datetime.now():
                        flash("Cannot register visitors for past date/time", "error")
                    else:
                        cursor.execute(
                            "UPDATE visitors SET visitor_name = ?, visit_date = ?, visit_time = ? WHERE id = ? AND student_id = ?",
                            (visitor_name, visit_date, visit_time, visitor_id, session['student_id'])
                        )
                        conn.commit()
                        flash("Visitor registration updated successfully", "success")
                except ValueError:
                    flash("Invalid date or time format", "error")
                except Exception as e:
                    conn.rollback()
                    flash("Error updating visitor. Please try again.", "error")
        else:
            if not all([visitor_name, visit_date, visit_time]):
                flash("Please fill in all fields", "error")
                visitors = cursor.execute(
                    "SELECT * FROM visitors WHERE student_id = ? ORDER BY visit_date DESC",
                    (session['student_id'],)
                ).fetchall()
                conn.close()
                return render_template("visitor.html", visitors=visitors)
            
            try:
                visit_datetime = datetime.strptime(f"{visit_date} {visit_time}", "%Y-%m-%d %H:%M")
                if visit_datetime < datetime.now():
                    flash("Cannot register visitors for past date/time", "error")
                    visitors = cursor.execute(
                        "SELECT * FROM visitors WHERE student_id = ? ORDER BY visit_date DESC",
                        (session['student_id'],)
                    ).fetchall()
                    conn.close()
                    return render_template("visitor.html", visitors=visitors)
                
                cursor.execute(
                    "INSERT INTO visitors (student_id, visitor_name, visit_date, visit_time) VALUES (?, ?, ?, ?)",
                    (session['student_id'], visitor_name, visit_date, visit_time)
                )
                conn.commit()
                flash("Visitor registered successfully", "success")
            except ValueError:
                flash("Invalid date or time format", "error")
                visitors = cursor.execute(
                    "SELECT * FROM visitors WHERE student_id = ? ORDER BY visit_date DESC",
                    (session['student_id'],)
                ).fetchall()
                conn.close()
                return render_template("visitor.html", visitors=visitors)
            except Exception as e:
                conn.rollback()
                flash("Error registering visitor. Please try again.", "error")
    
    cursor.execute(
        "SELECT * FROM visitors WHERE student_id = ? ORDER BY visit_date DESC",
        (session['student_id'],)
    )
    visitors = cursor.fetchall()
    
    conn.close()
    return render_template("visitor.html", visitors=visitors)

# EDIT VISITOR
@app.route("/visitor/edit/<int:visitor_id>")
@require_login
def edit_visitor(visitor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
        "SELECT * FROM visitors WHERE student_id = ? ORDER BY visit_date DESC",
        (session['student_id'],)
    )
    visitors = cursor.fetchall()
    
    conn.close()
    return render_template("visitor.html", visitors=visitors, editing_visitor=visitor)

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
@require_login
def chat():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
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
        conn.commit()
    except Exception as e:
        pass
    
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

if __name__ == "__main__":
    app.run(debug=True)
