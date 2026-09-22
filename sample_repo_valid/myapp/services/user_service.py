from myapp.repository.user_repository import UserRepository

class UserService:
    def __init__(self):
        self.repo = UserRepository()

    def fetch_user(self):
        return self.repo.find_by_id(1)
