from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import User, Site, SiteMember, Task, TaskReport, Message, UserRole, TaskStatus


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, telegram_id: int, phone: str, name: str, role: UserRole, lang: str = "ru") -> User:
    user = User(telegram_id=telegram_id, phone=phone, name=name, role=role, lang=lang)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_lang(session: AsyncSession, telegram_id: int, lang: str) -> None:
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(lang=lang)
    )
    await session.commit()


# ── Sites ──────────────────────────────────────────────────────────────────

async def create_site(session: AsyncSession, name: str, address: str, foreman_id: int, invite_code: str) -> Site:
    site = Site(name=name, address=address, foreman_id=foreman_id, invite_code=invite_code)
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def get_sites_by_foreman(session: AsyncSession, foreman_id: int) -> list[Site]:
    result = await session.execute(
        select(Site).where(Site.foreman_id == foreman_id).order_by(Site.created_at.desc())
    )
    return list(result.scalars().all())


async def get_site_by_id(session: AsyncSession, site_id: int) -> Site | None:
    result = await session.execute(
        select(Site).options(selectinload(Site.members).selectinload(SiteMember.worker))
        .where(Site.id == site_id)
    )
    return result.scalar_one_or_none()


async def get_site_by_invite_code(session: AsyncSession, code: str) -> Site | None:
    result = await session.execute(select(Site).where(Site.invite_code == code))
    return result.scalar_one_or_none()


async def get_sites_for_worker(session: AsyncSession, worker_id: int) -> list[Site]:
    result = await session.execute(
        select(Site)
        .join(SiteMember, SiteMember.site_id == Site.id)
        .where(SiteMember.worker_id == worker_id)
        .order_by(Site.created_at.desc())
    )
    return list(result.scalars().all())


async def is_member(session: AsyncSession, site_id: int, worker_id: int) -> bool:
    result = await session.execute(
        select(SiteMember).where(SiteMember.site_id == site_id, SiteMember.worker_id == worker_id)
    )
    return result.scalar_one_or_none() is not None


async def add_member(session: AsyncSession, site_id: int, worker_id: int) -> SiteMember:
    member = SiteMember(site_id=site_id, worker_id=worker_id)
    session.add(member)
    await session.commit()
    return member


async def get_site_worker_telegram_ids(session: AsyncSession, site_id: int) -> list[int]:
    result = await session.execute(
        select(User.telegram_id)
        .join(SiteMember, SiteMember.worker_id == User.id)
        .where(SiteMember.site_id == site_id)
    )
    return list(result.scalars().all())


async def get_all_site_participant_telegram_ids(session: AsyncSession, site: Site) -> list[int]:
    foreman_result = await session.execute(select(User).where(User.id == site.foreman_id))
    foreman = foreman_result.scalar_one_or_none()
    worker_ids = await get_site_worker_telegram_ids(session, site.id)
    result = list(worker_ids)
    if foreman:
        result.append(foreman.telegram_id)
    return list(set(result))


async def get_worker_lang(session: AsyncSession, worker_id: int) -> str:
    res = await session.execute(select(User.lang).where(User.id == worker_id))
    lang = res.scalar_one_or_none()
    return lang or "ru"


# ── Tasks ──────────────────────────────────────────────────────────────────

async def create_task(session: AsyncSession, site_id: int, title: str, description: str, created_by: int) -> Task:
    task = Task(site_id=site_id, title=title, description=description, created_by=created_by)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_tasks_by_site(session: AsyncSession, site_id: int) -> list[Task]:
    result = await session.execute(
        select(Task).where(Task.site_id == site_id).order_by(Task.created_at.desc())
    )
    return list(result.scalars().all())


async def get_task_by_id(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def take_task(session: AsyncSession, task_id: int, worker_id: int) -> None:
    await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(status=TaskStatus.in_progress, taken_by_id=worker_id)
    )
    await session.commit()


async def complete_task(session: AsyncSession, task_id: int) -> None:
    await session.execute(
        update(Task).where(Task.id == task_id).values(status=TaskStatus.done)
    )
    await session.commit()


async def create_report(session: AsyncSession, task_id: int, worker_id: int, comment: str, photos: list[str]) -> TaskReport:
    import json
    report = TaskReport(task_id=task_id, worker_id=worker_id, comment=comment, photos_json=json.dumps(photos))
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


# ── Messages ───────────────────────────────────────────────────────────────

async def save_message(session: AsyncSession, site_id: int, user_id: int, text: str, photo_id: str | None = None) -> Message:
    msg = Message(site_id=site_id, user_id=user_id, text=text, photo_id=photo_id)
    session.add(msg)
    await session.commit()
    return msg


async def get_recent_messages(session: AsyncSession, site_id: int, limit: int = 20) -> list[Message]:
    result = await session.execute(
        select(Message)
        .options(selectinload(Message.sender))
        .where(Message.site_id == site_id)
        .order_by(Message.sent_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))
