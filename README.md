# Student Dormitory Management Flask Application

A Flask web application for managing student dormitory bookings and facilities.

## Setup Instructions

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database:**
   ```bash
   python init_db.py
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Access the application:**
   Open your browser and navigate to: `http://127.0.0.1:5000`

## Project Structure

- `app.py` - Main Flask application file
- `db.py` - Database connection utilities
- `models.py` - Data models
- `init_db.py` - Database initialization script
- `templates/` - HTML templates
- `database/` - SQLite database files

## Routes

- `/` - Login page
- `/signup` - Sign up page
- `/dashboard` - Student dashboard
- `/search` - Search hostels
- `/hostels` - List all hostels
- `/hostel` - Hostel details
- `/room` - Room details
- `/booking` - Booking page
- `/payment` - Payment page
- `/confirmation` - Booking confirmation
- `/myunit` - My unit page
- `/facility` - Facility booking
- `/repair` - Repair request
- `/students` - List all students
