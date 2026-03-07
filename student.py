class Student:

    def __init__(self, name, student_id, email):
        self.name = name
        self.student_id = student_id
        self.email = email

    def login(self):
        print("Student logged in")

    def register(self):
        print("Student registered")