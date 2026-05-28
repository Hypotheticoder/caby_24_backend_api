import os
import time
import uuid

import redis

# Configure Redis from environment for local or Docker usage.
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


class PlatformGuard:
    @staticmethod
    def check_ban(user_id, user_type="driver"):
        # Checks if a ban key currently exists.
        # Keep the legacy key check for backwards compatibility.
        ban_keys = [f"banned:{user_type}:{user_id}"]
        if user_type == "driver":
            ban_keys.append(f"ban:driver:{user_id}")
        for ban_key in ban_keys:
            if r.exists(ban_key):
                ttl = r.ttl(ban_key)
                hours = ttl // 3600
                mins = (ttl % 3600) // 60
                return True, f"Account Suspended. Try again in {hours}h {mins}m."

        return False, ""

    @staticmethod
    def get_cancellation_count(user_type, user_id):
        key = f"cancellations:{user_type}:{user_id}"
        now = int(time.time())
        window_start = now - 86400  # Exactly 24 hours ago

        # Remove cancellations outside the rolling 24-hour window first.
        r.zremrangebyscore(key, "-inf", window_start)
        return r.zcard(key)

    @staticmethod
    def attempt_cancellation(user_type, user_id, limit):
        key = f"cancellations:{user_type}:{user_id}"
        now = int(time.time())
        window_start = now - 86400  # Exactly 24 hours ago

        # 1. Clean up old cancellations outside the 24h window
        r.zremrangebyscore(key, "-inf", window_start)

        # 2. Record the new cancellation first
        unique_val = f"{now}:{uuid.uuid4().hex[:6]}"
        r.zadd(key, {unique_val: now})
        r.expire(key, 86400)  # Let Redis clean up inactive keys

        # 3. Check the new total count
        current_count = PlatformGuard.get_cancellation_count(user_type, user_id)

        # 4. Apply the ban if the limit is breached
        if current_count >= limit:
            ban_key = f"banned:{user_type}:{user_id}"
            r.setex(ban_key, 86400, "true")  # 24-hour ban (86400 seconds)

            # Optional: Trigger specific webhooks or alerts based on user_type
            if user_type == "driver":
                print(f"Driver {user_id} suspended.")
            elif user_type == "customer":
                print(f"Customer {user_id} suspended.")

            # Keep legacy key around for existing callers until everything is migrated.
            r.setex(f"ban:driver:{user_id}", 86400, "Too many cancellations")

            return False
        return True
