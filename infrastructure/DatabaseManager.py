import os
import logging
from enum import Enum
from threading import Lock
from typing import AsyncGenerator, Dict, Optional
from contextlib import asynccontextmanager

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class DBEnvironment(str, Enum):
    DEV = "DEV"
    QA = "QA"


class DatabaseConfig(BaseSettings):
    db_type: str = Field(default="postgresql", alias="DB_TYPE")
    user: str = ""
    password: str = ""
    host: str = "localhost"
    port: Optional[int] = None
    name: str = ""
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def build_async_uri(self) -> str:
        engine_type = self.db_type.lower()
        if engine_type == "postgresql":
            port = self.port or 5432
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{port}/{self.name}"
        elif engine_type == "mysql":
            port = self.port or 3306
            return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{port}/{self.name}"
        elif engine_type == "mssql":
            port = self.port or 1433
            return f"mssql+aioodbc://{self.user}:{self.password}@{self.host}:{port}/{self.name}?driver=ODBC+Driver+17+for+SQL+Server"
        
        raise ValueError(f"Motor '{engine_type}' no soportado en modo asíncrono.")


class DatabaseManager:
    _instances: Dict[DBEnvironment, "DatabaseManager"] = {}
    _lock: Lock = Lock()

    def __new__(cls, env: DBEnvironment) -> "DatabaseManager":
        with cls._lock:
            if env not in cls._instances:
                instance = super(DatabaseManager, cls).__new__(cls)
                instance._init_engine(env)
                cls._instances[env] = instance
            return cls._instances[env]

    def _init_engine(self, env: DBEnvironment) -> None:
        prefix = f"DB_{env.value}_"
        config = DatabaseConfig(
            _env_prefix=prefix,
            DB_TYPE=os.getenv("DB_TYPE", "postgresql"),
            user=os.getenv(f"DB_USER_{env.value}", ""),
            password=os.getenv(f"DB_PASSWORD_{env.value}", ""),
            host=os.getenv(f"DB_HOST_{env.value}", "localhost"),
            port=int(os.getenv(f"DB_PORT_{env.value}")) if os.getenv(f"DB_PORT_{env.value}") else None,
            name=os.getenv(f"DB_NAME_{env.value}", ""),
        )

        self.engine: AsyncEngine = create_async_engine(
            config.build_async_uri(),
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=True,
        )
        self.SessionFactory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        session: AsyncSession = self.SessionFactory()
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Error en la transacción [Entorno DB]: %s", exc)
            raise exc
        finally:
            await session.close()

    async def dispose_pool(self) -> None:
        await self.engine.dispose()