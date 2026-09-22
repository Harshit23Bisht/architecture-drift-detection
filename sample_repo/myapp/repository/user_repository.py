import json

class UserRepository:
    def fetch_user(self):
        return json.dumps({"id": 1, "name": "Alice"})
