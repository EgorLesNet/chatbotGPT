from sqlalchemy import select, delete, update
from db.models import Site, SiteMember, Task, TaskReport, User, Message, UserRole, TaskStatus, TaskReview
import json


async def get_user_by_tg(session, telegram_id: int):
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()


async def get_user_by_phone(session, phone: str):
    res = await session.execute(select(User).where(User.phone == phone))
    return res.scalar_one_or_none()


async def create_user(session, telegram_id: int, phone: str, name: str, role: UserRole, lang: str = "ru"):
    user = User(telegram_id=telegram_id, phone=phone, name=name, role=role, lang=lang)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_site(session, name: str, address: str, foreman_id: int, invite_code: str, photos=None, videos=None):
    site = Site(
        name=name,
        address=address,
        foreman_id=foreman_id,
        invite_code=invite_code,
        photos_json=json.dumps(photos or []),
        videos_json=json.dumps(videos or []),
    )
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def get_site_by_invite(session, invite_code: str):
    res = await session.execute(select(Site).where(Site.invite_code == invite_code))
    return res.scalar_one_or_none()


async def add_worker_to_site(session, site_id: int, worker_id: int):
    member = SiteMember(site_id=site_id, worker_id=worker_id)
    session.add(member)
    await session.commit()
    return member


async def is_worker_on_site(session, site_id: int, worker_id: int) -> bool:
    res = await session.execute(
        select(SiteMember).where(SiteMember.site_id == site_id, SiteMember.worker_id == worker_id)
    )
    return res.scalar_one_or_none() is not None


async def get_sites_by_foreman(session, foreman_id: int):
    res = await session.execute(select(Site).where(Site.foreman_id == foreman_id))
    return list(res.scalars().all())


async def get_sites_for_worker(session, worker_id: int):
    res = await session.execute(
        select(Site).join(SiteMember, SiteMember.site_id == Site.id).where(SiteMember.worker_id == worker_id)
    )
    return list(res.scalars().all())


async def get_site_by_id(session, site_id: int):
    res = await session.execute(select(Site).where(Site.id == site_id))
    return res.scalar_one_or_none()


async def create_task(session, site_id: int, title: str, description: str, created_by: int, photo_id: str | None = None):
    task = Task(site_id=site_id, title=title, description=description, created_by=created_by, photo_id=photo_id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_tasks_by_site(session, site_id: int):
    res = await session.execute(select(Task).where(Task.site_id == site_id).order_by(Task.created_at.desc()))
    return list(res.scalars().all())


async def get_task_by_id(session, task_id: int):
    res = await session.execute(select(Task).where(Task.id == task_id))
    return res.scalar_one_or_none()


async def take_task(session, task_id: int, worker_id: int):
    await session.execute(
        update(Task).where(Task.id == task_id, Task.status == TaskStatus.open).values(
            status=TaskStatus.in_progress,
            taken_by_id=worker_id,
        )
    )
    await session.commit()


async def send_task_to_review(session, task_id: int):
    await session.execute(update(Task).where(Task.id == task_id).values(status=TaskStatus.review))
    await session.commit()


async def return_task_to_work(session, task_id: int):
    await session.execute(update(Task).where(Task.id == task_id).values(status=TaskStatus.in_progress))
    await session.commit()


async def complete_task(session, task_id: int):
    await session.execute(update(Task).where(Task.id == task_id).values(status=TaskStatus.done))
    await session.commit()


async def delete_task(session, task_id: int):
    await session.execute(delete(Task).where(Task.id == task_id))
    await session.commit()


async def create_report(session, task_id: int, worker_id: int, comment: str, photos: list[str]):
    res = await session.execute(select(TaskReport).where(TaskReport.task_id == task_id))
    existing = res.scalar_one_or_none()
    if existing:
        existing.worker_id = worker_id
        existing.comment = comment
        existing.photos_json = json.dumps(photos)
        await session.commit()
        await session.refresh(existing)
        return existing
    report = TaskReport(task_id=task_id, worker_id=worker_id, comment=comment, photos_json=json.dumps(photos))
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_report_by_task(session, task_id: int):
    res = await session.execute(select(TaskReport).where(TaskReport.task_id == task_id))
    return res.scalar_one_or_none()


async def create_task_review(session, task_id: int, foreman_id: int, comment: str):
    review = TaskReview(task_id=task_id, foreman_id=foreman_id, comment=comment)
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def get_last_task_review(session, task_id: int):
    res = await session.execute(select(TaskReview).where(TaskReview.task_id == task_id).order_by(TaskReview.created_at.desc()))
    return res.scalars().first()


async def get_workers_by_site(session, site_id: int):
    res = await session.execute(
        select(User)
        .join(SiteMember, SiteMember.worker_id == User.id)
        .where(SiteMember.site_id == site_id, User.role == UserRole.worker)
    )
    return list(res.scalars().all())


async def get_site_worker_telegram_ids(session, site_id: int):
    res = await session.execute(
        select(User.telegram_id)
        .join(SiteMember, SiteMember.worker_id == User.id)
        .where(SiteMember.site_id == site_id, User.role == UserRole.worker)
    )
    return [row[0] for row in res.all()]


async def save_message(session, site_id: int, user_id: int, text: str, photo_id: str | None = None):
    msg = Message(site_id=site_id, user_id=user_id, text=text, photo_id=photo_id)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def get_recent_messages(session, site_id: int, limit: int = 20):
    res = await session.execute(
        select(Message).where(Message.site_id == site_id).order_by(Message.sent_at.desc()).limit(limit)
    )
    messages = list(res.scalars().all())
    messages.reverse()
    return messages
