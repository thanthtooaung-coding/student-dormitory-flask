class Booking:

    def __init__(self, student, room, checkin_date):
        self.student = student
        self.room = room
        self.checkin_date = checkin_date

    def confirm_booking(self):
        print("Booking confirmed")