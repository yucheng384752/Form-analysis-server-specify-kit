"""
Database configuration and session management.

Provides async SQLAlchemy setup with PostgreSQL, connection pooling,
and dependency injection for FastAPI routes.
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# Database engine and session factory (initialized during startup)
engine = None
async_session_factory = None


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def init_db() -> None:
    """
    Initialize database engine and session factory.
    
    This should be called during application startup.
    Only supports PostgreSQL database.
    """
    global engine, async_session_factory
    
    settings = get_settings()
    
    # Validate that we're using PostgreSQL
    if not settings.database_url.startswith('postgresql'):
        raise ValueError(
            f"只支援PostgreSQL資料庫。當前配置: {settings.database_url[:20]}..."
        )
    
    # Create async engine with connection pooling
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,  # Enable SQL logging in development
        pool_size=settings.database_pool_size,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=True,  # Validate connections before use
    )
    
    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    
    Provides async database session with automatic cleanup.
    Use this as a FastAPI dependency.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    if async_session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during startup."
        )
    
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database session.
    
    Use this for database operations outside of FastAPI routes.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        async with get_db_context() as db:
            user = await db.get(User, user_id)
        ```
    """
    if async_session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during startup."
        )
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """
    Close database engine.
    
    This should be called during application shutdown.
    """
    global engine
    if engine:
        await engine.dispose()
        engine = None