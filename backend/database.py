from __future__ import annotations

from datetime import date, datetime
from typing import AsyncGenerator, Iterable, List, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base, PortfolioPosition, PriceCache, User, WatchlistAlert, WatchlistItem

DATABASE_URL = "sqlite+aiosqlite:///./market.db"

# Асинхронный движок SQLAlchemy для SQLite.
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Создает таблицы в базе данных при первом запуске."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Легкая авто-миграция для старых SQLite-файлов:
        # раньше таблица watchlist могла быть без user_id.
        columns_result = await conn.execute(text("PRAGMA table_info(watchlist)"))
        column_names = {row[1] for row in columns_result.fetchall()}
        if "user_id" not in column_names:
            await conn.execute(text("ALTER TABLE watchlist ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watchlist_user_id ON watchlist(user_id)"))


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД в FastAPI."""
    async with SessionLocal() as session:
        yield session


async def create_user(session: AsyncSession, email: str, password_hash: str) -> User:
    """Создает нового пользователя."""
    user = User(email=email.lower().strip(), password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Находит пользователя по email."""
    return await session.scalar(select(User).where(User.email == email.lower().strip()))


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Находит пользователя по идентификатору."""
    return await session.scalar(select(User).where(User.id == user_id))


async def add_to_watchlist(session: AsyncSession, user_id: int, ticker: str) -> WatchlistItem:
    """Добавляет тикер в избранное пользователя (если еще не добавлен)."""
    normalized = ticker.strip().upper()

    existing = await session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.ticker == normalized,
        )
    )
    if existing:
        return existing

    item = WatchlistItem(user_id=user_id, ticker=normalized)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def remove_from_watchlist(session: AsyncSession, user_id: int, ticker: str) -> bool:
    """Удаляет тикер из избранного пользователя. Возвращает True, если запись удалена."""
    normalized = ticker.strip().upper()
    result = await session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.ticker == normalized,
        )
    )
    await session.commit()
    return (result.rowcount or 0) > 0


async def get_watchlist(session: AsyncSession, user_id: int) -> List[WatchlistItem]:
    """Возвращает текущий список избранных тикеров пользователя."""
    result = await session.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.added_at.desc())
    )
    return list(result.all())


async def save_price_history(
    session: AsyncSession,
    ticker: str,
    candles: Iterable[dict],
) -> None:
    """Сохраняет список свечей в кэш БД, пропуская уже существующие даты."""
    normalized = ticker.strip().upper()

    for candle in candles:
        candle_date = candle["date"]
        existing = await session.scalar(
            select(PriceCache).where(
                PriceCache.ticker == normalized,
                PriceCache.date == candle_date,
            )
        )
        if existing:
            continue

        session.add(
            PriceCache(
                ticker=normalized,
                date=candle_date,
                open=candle["open"],
                high=candle["high"],
                low=candle["low"],
                close=candle["close"],
                volume=candle["volume"],
            )
        )

    await session.commit()


async def upsert_portfolio_position(
    session: AsyncSession,
    user_id: int,
    ticker: str,
    market: str,
    weight_pct: float,
) -> PortfolioPosition:
    """Добавляет или обновляет позицию в портфеле."""
    normalized = ticker.strip().upper()
    market_norm = market.lower().strip()
    existing = await session.scalar(
        select(PortfolioPosition).where(
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.ticker == normalized,
        )
    )
    if existing:
        existing.market = market_norm
        existing.weight_pct = weight_pct
        await session.commit()
        await session.refresh(existing)
        return existing

    item = PortfolioPosition(
        user_id=user_id,
        ticker=normalized,
        market=market_norm,
        weight_pct=weight_pct,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def remove_portfolio_position(session: AsyncSession, user_id: int, ticker: str) -> bool:
    normalized = ticker.strip().upper()
    result = await session.execute(
        delete(PortfolioPosition).where(
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.ticker == normalized,
        )
    )
    await session.commit()
    return (result.rowcount or 0) > 0


async def get_portfolio(session: AsyncSession, user_id: int) -> List[PortfolioPosition]:
    result = await session.scalars(
        select(PortfolioPosition)
        .where(PortfolioPosition.user_id == user_id)
        .order_by(PortfolioPosition.added_at.desc())
    )
    return list(result.all())


async def get_cached_history(
    session: AsyncSession,
    ticker: str,
    from_date: date,
    to_date: date,
) -> List[PriceCache]:
    """Возвращает кэшированные свечи за указанный период."""
    normalized = ticker.strip().upper()
    result = await session.scalars(
        select(PriceCache)
        .where(
            PriceCache.ticker == normalized,
            PriceCache.date >= from_date,
            PriceCache.date <= to_date,
        )
        .order_by(PriceCache.date.asc())
    )
    return list(result.all())


async def upsert_watchlist_alert(
    session: AsyncSession,
    user_id: int,
    ticker: str,
    alert_type: str,
    threshold_value: float,
) -> WatchlistAlert:
    normalized = ticker.strip().upper()
    alert_type_norm = alert_type.strip().lower()
    existing = await session.scalar(
        select(WatchlistAlert).where(
            WatchlistAlert.user_id == user_id,
            WatchlistAlert.ticker == normalized,
            WatchlistAlert.alert_type == alert_type_norm,
        )
    )
    if existing:
        existing.threshold_value = threshold_value
        await session.commit()
        await session.refresh(existing)
        return existing

    item = WatchlistAlert(
        user_id=user_id,
        ticker=normalized,
        alert_type=alert_type_norm,
        threshold_value=threshold_value,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def remove_watchlist_alert(
    session: AsyncSession,
    user_id: int,
    alert_id: int,
) -> bool:
    result = await session.execute(
        delete(WatchlistAlert).where(
            WatchlistAlert.user_id == user_id,
            WatchlistAlert.id == alert_id,
        )
    )
    await session.commit()
    return (result.rowcount or 0) > 0


async def get_watchlist_alerts(session: AsyncSession, user_id: int) -> List[WatchlistAlert]:
    result = await session.scalars(
        select(WatchlistAlert)
        .where(WatchlistAlert.user_id == user_id)
        .order_by(WatchlistAlert.created_at.desc())
    )
    return list(result.all())


# Пример использования:
# async with SessionLocal() as session:
#     await add_to_watchlist(session, user_id=1, ticker="SBER")
#     items = await get_watchlist(session, user_id=1)
