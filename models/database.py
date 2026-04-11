from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    connections: Mapped[list["Connection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    panel_port: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_username: Mapped[str] = mapped_column(String(64), nullable=False)
    panel_password: Mapped[str] = mapped_column(String(256), nullable=False)
    inbound_id: Mapped[int] = mapped_column(Integer, nullable=False)
    max_clients: Mapped[int] = mapped_column(Integer, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    connections: Mapped[list["Connection"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False)
    xui_client_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped["User"] = relationship(back_populates="connections")
    server: Mapped["Server"] = relationship(back_populates="connections")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    yukassa_payment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | succeeded | cancelled
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
 
    user: Mapped["User"] = relationship(back_populates="payments")
    