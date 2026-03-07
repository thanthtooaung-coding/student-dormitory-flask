# models.py - Student Dormitory Management System Models

class Student:
    """Student model representing a student user"""
    
    def __init__(self, student_id, name, email_kmitl, password, faculty=None, major=None):
        self.student_id = student_id
        self.name = name
        self.email_kmitl = email_kmitl
        self.password = password
        self.faculty = faculty
        self.major = major
    
    def login(self):
        """Authenticate student login"""
        return True
    
    def search_hostel(self):
        """Search for available hostels"""
        return True
    
    def book_room(self):
        """Book a room in a hostel"""
        return True


class DormManager:
    """Dormitory Manager model"""
    
    def __init__(self, manager_id, name, phone_number=None, line_id=None):
        self.manager_id = manager_id
        self.name = name
        self.phone_number = phone_number
        self.line_id = line_id
    
    def manage_hostel(self):
        """Manage hostel operations"""
        return True
    
    def update_ticket_status(self):
        """Update status of support tickets"""
        return True


class Hostel:
    """Hostel model representing a dormitory building"""
    
    def __init__(self, hostel_id, name, location, distance_from_campus=None, rating=None):
        self.hostel_id = hostel_id
        self.name = name
        self.location = location
        self.distance_from_campus = distance_from_campus
        self.rating = rating
    
    def get_available_rooms(self):
        """Get list of available rooms in the hostel"""
        return []


class Room:
    """Room model representing a room in a hostel"""
    
    def __init__(self, room_id, room_type, price, facilities=None, availability=True, hostel_id=None):
        self.room_id = room_id
        self.room_type = room_type
        self.price = price
        self.facilities = facilities if facilities else []
        self.availability = availability
        self.hostel_id = hostel_id
    
    def lock_room(self):
        """Lock the room"""
        self.availability = False
        return True
    
    def unlock_room(self):
        """Unlock the room"""
        self.availability = True
        return True
    
    def check_availability(self):
        """Check if room is available"""
        return self.availability


class Booking:
    """Booking model representing a room booking"""
    
    def __init__(self, booking_id, student_id, room_id, checkin_date, booking_status="pending"):
        self.booking_id = booking_id
        self.student_id = student_id
        self.room_id = room_id
        self.checkin_date = checkin_date
        self.booking_status = booking_status
    
    def create_booking(self):
        """Create a new booking"""
        self.booking_status = "pending"
        return True
    
    def confirm_booking(self):
        """Confirm the booking"""
        self.booking_status = "confirmed"
        return True
    
    def cancel_booking(self):
        """Cancel the booking"""
        self.booking_status = "cancelled"
        return True


class Payment:
    """Payment model representing a payment transaction"""
    
    def __init__(self, payment_id, amount, payment_method, payment_status="pending"):
        self.payment_id = payment_id
        self.amount = amount
        self.payment_method = payment_method
        self.payment_status = payment_status
    
    def generate_prompt_pay_qr(self):
        """Generate PromptPay QR code for payment"""
        return "QR_CODE_STRING"
    
    def process_payment(self):
        """Process the payment"""
        self.payment_status = "completed"
        return True


class Bill:
    """Bill model representing a bill/invoice"""
    
    def __init__(self, bill_id, bill_type, amount, due_date, student_id=None):
        self.bill_id = bill_id
        self.type = bill_type
        self.amount = amount
        self.due_date = due_date
        self.student_id = student_id
    
    def calculate_bill(self):
        """Calculate the bill amount"""
        return self.amount
    
    def pay_bill(self):
        """Mark bill as paid"""
        return True


class Parcel:
    """Parcel model representing a package/parcel"""
    
    def __init__(self, parcel_id, sender, arrival_date, status="pending", student_id=None):
        self.parcel_id = parcel_id
        self.sender = sender
        self.arrival_date = arrival_date
        self.status = status
        self.student_id = student_id
    
    def update_pickup_status(self):
        """Update the pickup status of the parcel"""
        self.status = "picked_up"
        return True


class FacilityBooking:
    """Facility Booking model for booking facilities"""
    
    def __init__(self, facility_id, facility_name, booking_date, student_id=None):
        self.facility_id = facility_id
        self.facility_name = facility_name
        self.booking_date = booking_date
        self.student_id = student_id
    
    def reserve_facility(self):
        """Reserve a facility"""
        return True
    
    def timeslot(self):
        """Get available timeslots"""
        return []


class RepairRequest:
    """Repair Request model for maintenance requests"""
    
    def __init__(self, repair_id, issue_type, description, status="pending", report_date=None, student_id=None):
        self.repair_id = repair_id
        self.issue_type = issue_type
        self.description = description
        self.status = status
        self.report_date = report_date
        self.student_id = student_id
    
    def submit_request(self):
        """Submit a repair request"""
        self.status = "submitted"
        return True
    
    def update_status(self, new_status):
        """Update the status of the repair request"""
        self.status = new_status
        return True


class Visitor:
    """Visitor model representing a visitor"""
    
    def __init__(self, visitor_id, visitor_name, visit_date, visit_time, student_id=None):
        self.visitor_id = visitor_id
        self.visitor_name = visitor_name
        self.visit_date = visit_date
        self.visit_time = visit_time
        self.student_id = student_id
    
    def register_visitor(self):
        """Register a visitor"""
        return True
