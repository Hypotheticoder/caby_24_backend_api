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
    def check_ban(user_id):
        # Checks if a ban key currently exists
        if r.exists(f"ban:driver:{user_id}"):
            ttl = r.ttl(f"ban:driver:{user_id}")
            hours = ttl // 3600
            mins = (ttl % 3600) // 60
            return True, f"Account Suspended. Try again in {hours}h {mins}m."
        return False, ""

    @staticmethod
    def attempt_cancellation(user_type, user_id, limit):
        key = f"cancellations:{user_type}:{user_id}"
        now = int(time.time())
        window_start = now - 86400  # Exactly 24 hours ago

        # 1. Clean up old cancellations outside the 24h window
        r.zremrangebyscore(key, "-inf", window_start)

        # 2. Count current valid cancellations
        current_count = r.zcard(key)

        if current_count >= limit:
            # Trigger driver ban if they hit the limit
            if user_type == "driver":
                r.setex(f"ban:driver:{user_id}", 86400, "Too many cancellations")
            return False

        # 3. Success: Add new cancellation timestamp
        unique_val = f"{now}:{uuid.uuid4().hex[:6]}"
        r.zadd(key, {unique_val: now})
        r.expire(key, 86400)  # Let Redis clean up inactive keys

        return True
