import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import DATABASE_URL

logger = logging.getLogger(__name__)

Base = declarative_base()

DEFAULT_LOG_LIMIT = 50


class LLMLog(Base):
    """Main log table for agent executions."""

    __tablename__ = "llm_logs"

    id = Column(Integer, primary_key=True)
    agent_name = Column(String)
    provider = Column(String)
    model = Column(String)
    user_prompt = Column(Text)
    instructions = Column(Text)
    total_input_tokens = Column(Integer)
    total_output_tokens = Column(Integer)
    assistant_answer = Column(Text)
    raw_json = Column(Text)
    input_cost = Column(Float)
    output_cost = Column(Float)
    total_cost = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    checks = relationship(
        "EvalCheck", back_populates="log", cascade="all, delete-orphan"
    )
    guardrail_events = relationship(
        "GuardrailEvent", back_populates="log", cascade="all, delete-orphan"
    )


class EvalCheck(Base):
    """Evaluation check results."""

    __tablename__ = "eval_checks"

    id = Column(Integer, primary_key=True)
    log_id = Column(
        Integer, ForeignKey("llm_logs.id", ondelete="CASCADE"), nullable=False
    )
    check_name = Column(String, nullable=False)
    passed = Column(Boolean)
    score = Column(Float)
    details = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    log = relationship("LLMLog", back_populates="checks")


class GuardrailEvent(Base):
    """Guardrail monitoring events."""

    __tablename__ = "guardrail_events"

    id = Column(Integer, primary_key=True)
    log_id = Column(
        Integer, ForeignKey("llm_logs.id", ondelete="CASCADE"), nullable=False
    )
    guardrail_name = Column(String, nullable=False)
    triggered = Column(Boolean, nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    log = relationship("LLMLog", back_populates="guardrail_events")


# Global engine and session factory
_engine: Any | None = None
_SessionLocal: Any | None = None


def _get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            logger.error("DATABASE_URL not set in environment")
            return None
        try:
            _engine = create_engine(DATABASE_URL)
            logger.info("Database engine created")
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}", exc_info=True)
            return None
    return _engine


@contextmanager
def get_db():
    """Get database session as context manager."""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set, database unavailable")
        yield None
        return

    global _SessionLocal
    if _SessionLocal is None:
        engine = _get_engine()
        if not engine:
            yield None
            return
        _SessionLocal = sessionmaker(bind=engine)

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize database - create tables if they don't exist."""
    if not DATABASE_URL:
        logger.error("Cannot initialize database: DATABASE_URL not set")
        return

    try:
        engine = _get_engine()
        if not engine:
            logger.error("Failed to get database engine")
            return
        Base.metadata.create_all(engine)
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)


def insert_log(db: Any, **kwargs) -> int | None:
    """Insert log record and return ID."""
    if not db:
        logger.warning("Database session not available, cannot insert log")
        return None

    try:
        record = LLMLog(**kwargs)
        db.add(record)
        db.flush()
        return record.id
    except Exception as e:
        logger.error(f"Failed to insert log: {e}", exc_info=True)
        return None


def insert_eval_check(db: Any, **kwargs) -> int | None:
    """Insert evaluation check."""
    if not db:
        logger.warning("Database session not available, cannot insert eval check")
        return None

    try:
        record = EvalCheck(**kwargs)
        db.add(record)
        db.flush()
        return record.id
    except Exception as e:
        logger.error(f"Failed to insert eval check: {e}", exc_info=True)
        return None


def insert_guardrail_event(db: Any, **kwargs) -> int | None:
    """Insert guardrail event."""
    if not db:
        logger.warning("Database session not available, cannot insert guardrail event")
        return None

    try:
        record = GuardrailEvent(**kwargs)
        db.add(record)
        db.flush()
        return record.id
    except Exception as e:
        logger.error(f"Failed to insert guardrail event: {e}", exc_info=True)
        return None


def get_recent_logs(limit: int = DEFAULT_LOG_LIMIT) -> list[dict]:
    """Get recent logs for display."""
    try:
        with get_db() as db:
            if not db:
                return []

            logs = (
                db.query(LLMLog).order_by(LLMLog.created_at.desc()).limit(limit).all()
            )
            return [
                {
                    "id": log.id,
                    "created_at": log.created_at,
                    "agent_name": log.agent_name,
                    "model": log.model,
                    "user_prompt": log.user_prompt,
                    "total_cost": log.total_cost,
                    "total_input_tokens": log.total_input_tokens,
                    "total_output_tokens": log.total_output_tokens,
                }
                for log in logs
            ]
    except Exception as e:
        logger.error(f"get_recent_logs failed: {e}", exc_info=True)
        return []


def get_cost_stats() -> dict:
    """Get cost statistics."""
    try:
        with get_db() as db:
            if not db:
                return {"total_cost": 0.0, "total_queries": 0, "avg_cost": 0.0}

            result = db.query(
                func.sum(LLMLog.total_cost).label("total_cost"),
                func.count(LLMLog.id).label("total_queries"),
            ).first()

            total_cost = float(result.total_cost or 0.0)
            total_queries = int(result.total_queries or 0)
            avg_cost = total_cost / total_queries if total_queries > 0 else 0.0

            return {
                "total_cost": total_cost,
                "total_queries": total_queries,
                "avg_cost": avg_cost,
            }
    except Exception as e:
        logger.error(f"get_cost_stats failed: {e}", exc_info=True)
        return {"total_cost": 0.0, "total_queries": 0, "avg_cost": 0.0}
