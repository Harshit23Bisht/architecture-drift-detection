from myapp.services.audit_service import AuditService
from myapp.repository.user_repository import UserRepository

class UserService:
    def __init__(self):
        self.repo = UserRepository()
        self.audit = AuditService()

    def get_user(self):
        self.audit.log("get_user")
        return self.repo.fetch_user()
