from aiogram import Bot


async def notify_many(bot: Bot, telegram_ids: list[int], text: str, exclude: int | None = None) -> None:
    for tg_id in telegram_ids:
        if exclude and tg_id == exclude:
            continue
        try:
            await bot.send_message(tg_id, text)
        except Exception:
            pass
