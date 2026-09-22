import os
from myapp.services.user_service import UserService
from myapp.repository.user_repository import UserRepository

class UserController:
    def __init__(self):
        self.service = UserService()
        self.repo = UserRepository()  # Injected Violation: Controller bypassing Service to call Repository

    def handle_request(self):
        print(os.name)
        return self.service.get_user()
