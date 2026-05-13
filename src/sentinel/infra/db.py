from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import AsyncGenerator
from datetime import date, datetime, time, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://sentinel:password@localhost:5432/sentinel",
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    broker_server: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vault_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_s3_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    is_baseline_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    maturity_state: Mapped[str] = mapped_column(String(32), default="maturity_0")
    enforce_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    initial_parameters: Mapped[dict[str, float | str]] = mapped_column(JSON, default=dict)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ApiCredential(Base):
    __tablename__ = "api_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(128))
    api_key_hash: Mapped[str] = mapped_column(String(128))
    api_key_last4: Mapped[str] = mapped_column(String(4))
    helm_release: Mapped[str] = mapped_column(String(255))
    helm_command: Mapped[str] = mapped_column(Text)
    provisioning_state: Mapped[str] = mapped_column(String(64), default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class OnboardingJob(Base):
    __tablename__ = "onboarding_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    broker_server: Mapped[str] = mapped_column(String(255))
    account_id: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text, default="Job queued")
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    min_trades: Mapped[int] = mapped_column(Integer, default=100)
    model_s3_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskAudit(Base):
    __tablename__ = "risk_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    decision: Mapped[str] = mapped_column(String(32))
    risk_score: Mapped[float] = mapped_column(Float)
    size_multiplier: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(32))
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    top_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    explanation: Mapped[list[dict[str, float | str]]] = mapped_column(JSON, default=list)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class BehavioralLog(Base):
    __tablename__ = "behavioral_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_hash: Mapped[str] = mapped_column(String(64), index=True)
    audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    hour_decimal: Mapped[float] = mapped_column(Float)
    losing_streak: Mapped[int] = mapped_column(Integer)
    drawdown_state: Mapped[float] = mapped_column(Float)
    lot_deviation: Mapped[float] = mapped_column(Float)
    revenge_timer: Mapped[float] = mapped_column(Float)
    lots: Mapped[float] = mapped_column(Float)
    rr_ratio: Mapped[float] = mapped_column(Float)
    realized_vol_20: Mapped[float] = mapped_column(Float, default=0.0)
    trend_momentum: Mapped[float] = mapped_column(Float, default=0.0)
    decision: Mapped[str] = mapped_column(String(32))
    risk_score: Mapped[float] = mapped_column(Float)
    size_multiplier: Mapped[float] = mapped_column(Float)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
DB_AVAILABLE = True
_memory_users: dict[str, User] = {}
_memory_api_credentials: dict[str, ApiCredential] = {}
_memory_jobs: dict[str, OnboardingJob] = {}
_memory_audits: list[RiskAudit] = []
_memory_behavioral_logs: list[BehavioralLog] = []


def _sort_timestamp(value: datetime | None) -> datetime:
    return value or datetime.min.replace(tzinfo=timezone.utc)


def _hash_api_key(raw_api_key: str) -> str:
    return hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


async def init_db() -> None:
    global DB_AVAILABLE
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS maturity_state VARCHAR(32) DEFAULT 'maturity_0'")
            )
            await connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS enforce_mode BOOLEAN DEFAULT FALSE")
            )
            await connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS initial_parameters JSON DEFAULT '{}'::json")
            )
            await connection.execute(
                text("ALTER TABLE behavioral_logs DROP COLUMN IF EXISTS user_id")
            )
            await connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_behavioral_logs_user_hash_created ON behavioral_logs (user_hash, created_at)")
            )
        DB_AVAILABLE = True
    except Exception:
        DB_AVAILABLE = False


async def ping_db() -> bool:
    if not DB_AVAILABLE:
        return False
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_user(session: AsyncSession, user_id: str) -> User | None:
    if not DB_AVAILABLE:
        return _memory_users.get(user_id)

    try:
        result = await session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return _memory_users.get(user_id)


async def upsert_user(
    session: AsyncSession,
    user_id: str,
    broker_server: str | None = None,
    account_id: str | None = None,
    vault_path: str | None = None,
    model_s3_key: str | None = None,
    trade_count: int | None = None,
    is_baseline_ready: bool | None = None,
    trained_at: datetime | None = None,
    maturity_state: str | None = None,
    enforce_mode: bool | None = None,
    initial_parameters: dict[str, float | str] | None = None,
) -> User:
    user = await get_user(session, user_id)
    if user is None:
        user = User(user_id=user_id, trade_count=0, is_baseline_ready=False)
        if DB_AVAILABLE:
            session.add(user)

    if broker_server is not None:
        user.broker_server = broker_server
    if account_id is not None:
        user.account_id = account_id
    if vault_path is not None:
        user.vault_path = vault_path
    if model_s3_key is not None:
        user.model_s3_key = model_s3_key
    if trade_count is not None:
        user.trade_count = trade_count
    if is_baseline_ready is not None:
        user.is_baseline_ready = is_baseline_ready
    if trained_at is not None:
        user.trained_at = trained_at
    if maturity_state is not None:
        user.maturity_state = maturity_state
    if enforce_mode is not None:
        user.enforce_mode = enforce_mode
    if initial_parameters is not None:
        user.initial_parameters = initial_parameters

    if not DB_AVAILABLE:
        _memory_users[user_id] = user
        return user

    try:
        await session.commit()
        await session.refresh(user)
    except Exception:
        _memory_users[user_id] = user
    return user


async def get_api_credential(session: AsyncSession, user_id: str) -> ApiCredential | None:
    if not DB_AVAILABLE:
        return _memory_api_credentials.get(user_id)

    try:
        result = await session.execute(select(ApiCredential).where(ApiCredential.user_id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return _memory_api_credentials.get(user_id)


async def validate_api_key(session: AsyncSession, raw_api_key: str) -> bool:
    api_key_hash = _hash_api_key(raw_api_key)
    if not DB_AVAILABLE:
        return any(
            hmac.compare_digest(credential.api_key_hash, api_key_hash)
            for credential in _memory_api_credentials.values()
        )

    try:
        result = await session.execute(
            select(ApiCredential).where(ApiCredential.api_key_hash == api_key_hash)
        )
        credential = result.scalar_one_or_none()
        return credential is not None and hmac.compare_digest(
            credential.api_key_hash,
            api_key_hash,
        )
    except Exception:
        return any(
            hmac.compare_digest(credential.api_key_hash, api_key_hash)
            for credential in _memory_api_credentials.values()
        )


async def list_api_credentials(session: AsyncSession, limit: int = 200) -> list[ApiCredential]:
    if not DB_AVAILABLE:
        credentials = sorted(
            _memory_api_credentials.values(),
            key=lambda credential: _sort_timestamp(getattr(credential, "updated_at", None)),
            reverse=True,
        )
        return credentials[:limit]

    try:
        result = await session.execute(
            select(ApiCredential)
            .order_by(ApiCredential.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        credentials = sorted(
            _memory_api_credentials.values(),
            key=lambda credential: _sort_timestamp(getattr(credential, "updated_at", None)),
            reverse=True,
        )
        return credentials[:limit]


async def upsert_api_credential(
    session: AsyncSession,
    user_id: str,
    email: str,
    plan: str,
    raw_api_key: str,
    helm_release: str,
    helm_command: str,
    provisioning_state: str,
) -> ApiCredential:
    credential = await get_api_credential(session, user_id)
    if credential is None:
        credential = ApiCredential(
            user_id=user_id,
            email=email,
            plan=plan,
            api_key_hash=_hash_api_key(raw_api_key),
            api_key_last4=raw_api_key[-4:],
            helm_release=helm_release,
            helm_command=helm_command,
            provisioning_state=provisioning_state,
        )
        if DB_AVAILABLE:
            session.add(credential)
    else:
        credential.email = email
        credential.plan = plan
        credential.api_key_hash = _hash_api_key(raw_api_key)
        credential.api_key_last4 = raw_api_key[-4:]
        credential.helm_release = helm_release
        credential.helm_command = helm_command
        credential.provisioning_state = provisioning_state

    if not DB_AVAILABLE:
        _memory_api_credentials[user_id] = credential
        return credential

    try:
        await session.commit()
        await session.refresh(credential)
    except Exception:
        _memory_api_credentials[user_id] = credential
    return credential


async def create_onboarding_job(
    session: AsyncSession,
    job_id: str,
    user_id: str,
    broker_server: str,
    account_id: str,
    min_trades: int,
    state: str,
    message: str,
) -> OnboardingJob:
    job = OnboardingJob(
        job_id=job_id,
        user_id=user_id,
        broker_server=broker_server,
        account_id=account_id,
        min_trades=min_trades,
        state=state,
        message=message,
        trade_count=0,
    )
    if not DB_AVAILABLE:
        _memory_jobs[job_id] = job
        return job

    try:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    except Exception:
        _memory_jobs[job_id] = job
    return job


async def get_onboarding_job(session: AsyncSession, job_id: str) -> OnboardingJob | None:
    if not DB_AVAILABLE:
        return _memory_jobs.get(job_id)

    try:
        result = await session.execute(select(OnboardingJob).where(OnboardingJob.job_id == job_id))
        return result.scalar_one_or_none()
    except Exception:
        return _memory_jobs.get(job_id)


async def list_onboarding_jobs(session: AsyncSession, limit: int = 100) -> list[OnboardingJob]:
    if not DB_AVAILABLE:
        jobs = sorted(
            _memory_jobs.values(),
            key=lambda job: _sort_timestamp(getattr(job, "created_at", None)),
            reverse=True,
        )
        return jobs[:limit]

    try:
        result = await session.execute(
            select(OnboardingJob)
            .order_by(OnboardingJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        jobs = sorted(
            _memory_jobs.values(),
            key=lambda job: _sort_timestamp(getattr(job, "created_at", None)),
            reverse=True,
        )
        return jobs[:limit]


async def update_onboarding_job(
    session: AsyncSession,
    job_id: str,
    **fields: object,
) -> OnboardingJob | None:
    job = await get_onboarding_job(session, job_id)
    if job is None:
        return None

    for key, value in fields.items():
        if hasattr(job, key):
            setattr(job, key, value)

    job.updated_at = datetime.now(timezone.utc)
    if str(fields.get("state", "")) in {"ready", "failed", "blank_baseline"}:
        job.completed_at = datetime.now(timezone.utc)

    if not DB_AVAILABLE:
        _memory_jobs[job_id] = job
        return job

    try:
        await session.commit()
        await session.refresh(job)
    except Exception:
        _memory_jobs[job_id] = job
    return job


async def record_risk_audit(
    session: AsyncSession,
    user_id: str,
    symbol: str,
    decision: str,
    risk_score: float,
    size_multiplier: float,
    mode: str,
    is_anomaly: bool,
    top_reason: str | None,
    explanation: list[dict[str, float | str]],
    latency_ms: float,
    cached: bool,
) -> RiskAudit:
    audit = RiskAudit(
        user_id=user_id,
        symbol=symbol,
        decision=decision,
        risk_score=risk_score,
        size_multiplier=size_multiplier,
        mode=mode,
        is_anomaly=is_anomaly,
        top_reason=top_reason,
        explanation=explanation,
        latency_ms=latency_ms,
        cached=cached,
    )
    if not DB_AVAILABLE:
        _memory_audits.append(audit)
        return audit

    try:
        session.add(audit)
        await session.commit()
        await session.refresh(audit)
    except Exception:
        _memory_audits.append(audit)
    return audit


async def record_behavioral_log(
    session: AsyncSession,
    user_id: str,
    audit_id: int | None,
    symbol: str,
    hour_decimal: float,
    losing_streak: int,
    drawdown_state: float,
    lot_deviation: float,
    revenge_timer: float,
    lots: float,
    rr_ratio: float,
    realized_vol_20: float,
    trend_momentum: float,
    decision: str,
    risk_score: float,
    size_multiplier: float,
    is_anomaly: bool,
) -> BehavioralLog:
    log = BehavioralLog(
        user_hash=hash_user_id(user_id),
        audit_id=audit_id,
        symbol=symbol,
        hour_decimal=hour_decimal,
        losing_streak=losing_streak,
        drawdown_state=drawdown_state,
        lot_deviation=lot_deviation,
        revenge_timer=revenge_timer,
        lots=lots,
        rr_ratio=rr_ratio,
        realized_vol_20=realized_vol_20,
        trend_momentum=trend_momentum,
        decision=decision,
        risk_score=risk_score,
        size_multiplier=size_multiplier,
        is_anomaly=is_anomaly,
    )
    if not DB_AVAILABLE:
        _memory_behavioral_logs.append(log)
        return log

    try:
        session.add(log)
        await session.commit()
        await session.refresh(log)
    except Exception:
        _memory_behavioral_logs.append(log)
    return log


async def list_behavioral_logs(
    session: AsyncSession,
    user_id: str,
    limit: int = 500,
) -> list[BehavioralLog]:
    user_hash = hash_user_id(user_id)
    if not DB_AVAILABLE:
        logs = [log for log in _memory_behavioral_logs if log.user_hash == user_hash]
        logs = sorted(
            logs,
            key=lambda log: _sort_timestamp(getattr(log, "created_at", None)),
            reverse=True,
        )
        return logs[:limit]

    try:
        result = await session.execute(
            select(BehavioralLog)
            .where(BehavioralLog.user_hash == user_hash)
            .order_by(BehavioralLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        logs = [log for log in _memory_behavioral_logs if log.user_hash == user_hash]
        logs = sorted(
            logs,
            key=lambda log: _sort_timestamp(getattr(log, "created_at", None)),
            reverse=True,
        )
        return logs[:limit]


async def list_behavioral_logs_for_export(
    session: AsyncSession,
    export_date: date,
    limit: int = 100_000,
) -> list[BehavioralLog]:
    start = datetime.combine(export_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(export_date, time.max, tzinfo=timezone.utc)

    if not DB_AVAILABLE:
        logs = [
            log for log in _memory_behavioral_logs
            if start <= _sort_timestamp(getattr(log, "created_at", None)) <= end
        ]
        return sorted(logs, key=lambda log: _sort_timestamp(log.created_at))[:limit]

    try:
        result = await session.execute(
            select(BehavioralLog)
            .where(BehavioralLog.created_at >= start)
            .where(BehavioralLog.created_at <= end)
            .order_by(BehavioralLog.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        logs = [
            log for log in _memory_behavioral_logs
            if start <= _sort_timestamp(getattr(log, "created_at", None)) <= end
        ]
        return sorted(logs, key=lambda log: _sort_timestamp(log.created_at))[:limit]


async def update_risk_audit_explanation(
    session: AsyncSession,
    audit_id: int,
    explanation: list[dict[str, float | str]],
    top_reason: str | None,
) -> RiskAudit | None:
    if not DB_AVAILABLE:
        for audit in _memory_audits:
            if getattr(audit, "id", None) == audit_id:
                audit.explanation = explanation
                audit.top_reason = top_reason
                return audit
        return None

    try:
        result = await session.execute(select(RiskAudit).where(RiskAudit.id == audit_id))
        audit = result.scalar_one_or_none()
        if audit is not None:
            audit.explanation = explanation
            audit.top_reason = top_reason
            await session.commit()
            await session.refresh(audit)
        return audit
    except Exception:
        return None


async def list_risk_audits(
    session: AsyncSession,
    user_id: str | None = None,
    limit: int = 50,
) -> list[RiskAudit]:
    if not DB_AVAILABLE:
        audits = _memory_audits
        if user_id is not None:
            audits = [audit for audit in audits if audit.user_id == user_id]
        audits = sorted(
            audits,
            key=lambda audit: _sort_timestamp(getattr(audit, "created_at", None)),
            reverse=True,
        )
        return audits[:limit]

    try:
        query = select(RiskAudit)
        if user_id is not None:
            query = query.where(RiskAudit.user_id == user_id)
        query = query.order_by(RiskAudit.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception:
        audits = _memory_audits
        if user_id is not None:
            audits = [audit for audit in audits if audit.user_id == user_id]
        audits = sorted(
            audits,
            key=lambda audit: _sort_timestamp(getattr(audit, "created_at", None)),
            reverse=True,
        )
        return audits[:limit]


async def list_users(session: AsyncSession, limit: int = 200) -> list[User]:
    if not DB_AVAILABLE:
        users = sorted(
            _memory_users.values(),
            key=lambda user: _sort_timestamp(getattr(user, "updated_at", None)),
            reverse=True,
        )
        return users[:limit]

    try:
        result = await session.execute(
            select(User)
            .order_by(User.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        users = sorted(
            _memory_users.values(),
            key=lambda user: _sort_timestamp(getattr(user, "updated_at", None)),
            reverse=True,
        )
        return users[:limit]
