class Hostel:

    def __init__(self, name, location, rating):
        self.name = name
        self.location = location
        self.rating = rating

    def show_details(self):
        return f"{self.name} located at {self.location}"