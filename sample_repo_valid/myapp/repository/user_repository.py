class UserRepository:
    def find_by_id(self, user_id: int):
        return {"id": user_id, "status": "active"}
