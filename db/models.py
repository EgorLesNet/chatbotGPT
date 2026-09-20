import enum
from datetime import datetime
from sqlalchemy import (
    Integer, String, BigInteger, DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class UserRole(enum.Enum):
    foreman = "foreman"
    worker = "worker"


class TaskStatus(enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    foreman_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    members: Mapped[list["SiteMember"]] = relationship("SiteMember", back_populates="site", lazy="selectin")


class SiteMember(Base):
    __tablename__ = "site_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id"))
    worker_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    site: Mapped["Site"] = relationship("Site", back_populates="members")
    worker: Mapped["User"] = relationship("User", foreign_keys=[worker_id])


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.open)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    taken_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskReport(Base):
    __tablename__ = "task_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    worker_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    comment: Mapped[str] = mapped_column(Text, default="")
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    photo_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sender: Mapped["User"] = relationship("User", foreign_keys=[user_id])
