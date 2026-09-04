from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

from app.core.config import Settings, get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def build_engine(
    settings: Settings,
    *,
    poolclass: type[Pool] | None = None,
) -> Engine:
    """Create a SQLAlchemy engine with shared connection settings."""
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": settings.database_connect_timeout},
    }
    if poolclass is not None:
        engine_kwargs["poolclass"] = poolclass
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow
        engine_kwargs["pool_recycle"] = settings.database_pool_recycle

    return create_engine(settings.database_url, **engine_kwargs)


def get_engine() -> Engine:
    """Create or return the shared SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings())
    return _engine


class _LazyEngine:
    """Lazy proxy to the shared application engine."""

    def connect(self, *args: Any, **kwargs: Any) -> Any:
        return get_engine().connect(*args, **kwargs)

    def dispose(self) -> None:
        get_engine().dispose()

    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)


engine = _LazyEngine()


def get_session_factory() -> sessionmaker[Session]:
    """Create or return the shared session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request-scoped dependency injection."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def probe_database() -> bool:
    """Return True when PostgreSQL accepts a simple connectivity query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_database_state() -> None:
    """Reset cached engine state. Intended for tests only."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
