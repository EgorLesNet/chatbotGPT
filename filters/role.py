from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from db.models import UserRole


class RoleFilter(Filter):
    def __init__(self, role: UserRole):
        self.role = role

    async def __call__(self, event, current_user=None) -> bool:
        if not current_user:
            return False
        return current_user.role == self.role
