import random
from core.security_logic import r

OTP_EXPIRY_SECONDS = 300  # 5 minutes

def generate_and_save_otp(phone_number: str) -> str:
    # 10 9s override
    if phone_number == "9999999999":
        otp = "123456"
    else:
        otp = str(random.randint(100000, 999999))
    
    key = f"otp:{phone_number}"
    r.setex(key, OTP_EXPIRY_SECONDS, otp)
    return otp

def verify_otp(phone_number: str, otp: str) -> bool:
    # 10 9s override
    if phone_number == "9999999999" and otp == "123456":
        return True
        
    key = f"otp:{phone_number}"
    saved_otp = r.get(key)
    if saved_otp and saved_otp == otp:
        r.delete(key)  # Delete OTP after successful verification
        return True
    return False
