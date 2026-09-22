from myapp.services.user_service import UserService

class UserController:
    def __init__(self):
        self.service = UserService()

    def get_user_profile(self):
        return self.service.fetch_user()
