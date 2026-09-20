import json
from datetime import datetime
from sqlalchemy import (
    BigInteger, String, Text, DateTime, ForeignKey,
    Enum as SAEnum, Integer, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base
import enum


class UserRole(str, enum.Enum):
    foreman = "foreman"
    worker = "worker"


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sites_as_foreman: Mapped[list["Site"]] = relationship(back_populates="foreman")
    memberships: Mapped[list["SiteMember"]] = relationship(back_populates="worker")
    tasks_created: Mapped[list["Task"]] = relationship(back_populates="created_by_user")
    reports: Mapped[list["TaskReport"]] = relationship(back_populates="worker")
    messages: Mapped[list["Message"]] = relationship(back_populates="sender")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    foreman_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    foreman: Mapped["User"] = relationship(back_populates="sites_as_foreman")
    members: Mapped[list["SiteMember"]] = relationship(back_populates="site")
    tasks: Mapped[list["Task"]] = relationship(back_populates="site")
    messages: Mapped[list["Message"]] = relationship(back_populates="site")


class SiteMember(Base):
    __tablename__ = "site_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    site: Mapped["Site"] = relationship(back_populates="members")
    worker: Mapped["User"] = relationship(back_populates="memberships")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.open)
    taken_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    site: Mapped["Site"] = relationship(back_populates="tasks")
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by], back_populates="tasks_created")
    taken_by_user: Mapped["User | None"] = relationship(foreign_keys=[taken_by_id])
    reports: Mapped[list["TaskReport"]] = relationship(back_populates="task")


class TaskReport(Base):
    __tablename__ = "task_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str] = mapped_column(Text, default="")
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="reports")
    worker: Mapped["User"] = relationship(back_populates="reports")

    @property
    def photos(self) -> list[str]:
        return json.loads(self.photos_json)

    @photos.setter
    def photos(self, value: list[str]):
        self.photos_json = json.dumps(value)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    photo_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    site: Mapped["Site"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(back_populates="messages")
