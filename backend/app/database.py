import asyncio
from copy import deepcopy
from typing import AsyncIterator

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine, \
    async_scoped_session
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

MAX_SEARCH_TERMS = 5


class Base(DeclarativeBase):

    def to_dict(self, exclude: set[str] | str | None = None) -> dict:
        if exclude is None:
            exclude = set()
        if isinstance(exclude, str):
            exclude = {exclude}
        res = dict()
        for k in self.__mapper__.c.keys():
            if k in exclude:
                continue
            res[k] = self.__getattribute__(k)
        return deepcopy(res)


class DatabaseSessionManager:
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_maker = None
        self.session = None

    async def init_db(self):
        self.engine = create_async_engine(settings.database_url)

        from . import models  # Make sure all models are loaded
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
        )

        self.session = async_scoped_session(self.session_maker, scopefunc=asyncio.current_task)

    async def reset_db(self):
        """Drop all tables and recreate them. Used for debug/test fresh starts."""
        from . import models  # Make sure all models are loaded
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        if self.engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self.engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    session = sessionmanager.session()
    if session is None:
        raise Exception("DatabaseSessionManager is not initialized")
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


sessionmanager = DatabaseSessionManager()
