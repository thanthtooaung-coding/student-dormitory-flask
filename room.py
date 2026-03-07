class Room:

    def __init__(self, room_number, price, room_type):
        self.room_number = room_number
        self.price = price
        self.room_type = room_type

    def check_availability(self):
        return True