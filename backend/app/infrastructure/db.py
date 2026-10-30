from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_engine(url: str, pool_size: int = 5) -> AsyncEngine:
    # Пул соединений — ресурс процесса, а не состояние приложения. Итого соединений
    # = реплики × (pool_size + max_overflow); в проде перед БД ставят PgBouncer.
    return create_async_engine(url, pool_size=pool_size, max_overflow=pool_size, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
