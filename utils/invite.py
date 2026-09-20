import random
import string


def generate_invite_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def make_invite_link(bot_username: str, invite_code: str) -> str:
    return f"https://t.me/{bot_username}?start={invite_code}"
