"""
目标 FastAPI 模块化单体的 SQLAlchemy 地基。

Phase 1 只建立关系型数据库访问边界，暂不迁移 Java 仍负责的用户、
行程、计划等业务模块。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """未来 SQLAlchemy ORM model 的统一基类。"""


engine = create_engine(
    settings.build_database_url(),
    echo=settings.database_echo,
    pool_pre_ping=settings.database_pool_pre_ping,
    future=True,
)

# 每个请求使用独立 Session，后续 domain service 通过 get_db 依赖获取。
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 数据库依赖：为单个请求提供一个 SQLAlchemy Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
