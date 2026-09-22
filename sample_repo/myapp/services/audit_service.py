from myapp.services.user_service import UserService

class AuditService:
    def __init__(self):
        # Injected Circular Dependency: AuditService imports UserService, while UserService imports AuditService
        pass

    def log(self, event: str):
        print(f"Log event: {event}")
