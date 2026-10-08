"""FSM storage in the database, so conversation state survives serverless invocations."""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import text

from config import IS_POSTGRES
from db.base import engine


class PgStorage(BaseStorage):
    def __init__(self) -> None:
        self._ready = False

    @staticmethod
    def _key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{getattr(key, 'thread_id', None)}:{key.destiny}"

    async def _ensure(self) -> None:
        if self._ready:
            return
        async with engine.begin() as conn:
            await conn.execute(text(
                "create table if not exists fsm_states ("
                "key text primary key, state text, data text not null default '{}', updated_at timestamp not null)"
            ))
            if IS_POSTGRES:
                await conn.execute(text("alter table fsm_states enable row level security"))
            await conn.execute(
                text("delete from fsm_states where updated_at < :cutoff"),
                {"cutoff": datetime.utcnow() - timedelta(days=7)},
            )
        self._ready = True

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await self._ensure()
        value = state.state if isinstance(state, State) else state
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "insert into fsm_states (key, state, data, updated_at) values (:k, :s, '{}', :n) "
                    "on conflict (key) do update set state = excluded.state, updated_at = excluded.updated_at"
                ),
                {"k": self._key(key), "s": value, "n": datetime.utcnow()},
            )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        await self._ensure()
        async with engine.connect() as conn:
            row = (await conn.execute(
                text("select state from fsm_states where key = :k"), {"k": self._key(key)}
            )).first()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        await self._ensure()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "insert into fsm_states (key, state, data, updated_at) values (:k, null, :d, :n) "
                    "on conflict (key) do update set data = excluded.data, updated_at = excluded.updated_at"
                ),
                {"k": self._key(key), "d": json.dumps(data, default=str), "n": datetime.utcnow()},
            )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        await self._ensure()
        async with engine.connect() as conn:
            row = (await conn.execute(
                text("select data from fsm_states where key = :k"), {"k": self._key(key)}
            )).first()
        return json.loads(row[0]) if row and row[0] else {}

    async def close(self) -> None:
        return None
