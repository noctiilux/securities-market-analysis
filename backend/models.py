from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy моделей."""


class User(Base):
    """Модель пользователя приложения."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    watchlist_alerts: Mapped[list["WatchlistAlert"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    portfolio_positions: Mapped[list["PortfolioPosition"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class WatchlistItem(Base):
    """Модель избранных тикеров пользователя."""

    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="watchlist_items")


class WatchlistAlert(Base):
    """Уведомление по тикеру в избранном."""

    __tablename__ = "watchlist_alerts"
    __table_args__ = (UniqueConstraint("user_id", "ticker", "alert_type", name="uq_alert_user_ticker_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="watchlist_alerts")


class PortfolioPosition(Base):
    """Позиция в портфеле пользователя с долей веса."""

    __tablename__ = "portfolio_positions"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_portfolio_user_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="shares")
    weight_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    user: Mapped[User] = relationship(back_populates="portfolio_positions")


class PriceCache(Base):
    """Кэш исторических свечей по тикерам."""

    __tablename__ = "price_cache"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_price_cache_ticker_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0)


# Пример использования:
# from models import Base, User, WatchlistItem, PriceCache
