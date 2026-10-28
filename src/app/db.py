from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, create_engine, text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings

class UTCDateTime(TypeDecorator):
    """Data/hora sempre em UTC. No Postgres já era assim; o SQLite (robô leve) guarda sem fuso, então aqui convertemos
    na gravação/comparação e devolvemos com fuso na leitura (senão "hoje" e os horários saíam 3 h errados)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None and dialect.name == "sqlite":
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


engine = create_engine(settings.database_url, **({"connect_args": {"timeout": 30}} if settings.database_url.startswith("sqlite") else {}))

if engine.dialect.name == "sqlite":  # robô leve (Wyse): arquivo único; WAL = leitura (ctl) não trava a escrita e grava menos no disco
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, _record):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    product_key: Mapped[str | None] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(Text)  # título original da loja
    post_title: Mapped[str | None] = mapped_column(Text)  # título curto da IA, usado no post
    url: Mapped[str] = mapped_column(Text)
    affiliate_url: Mapped[str | None] = mapped_column(Text)
    monetized: Mapped[bool] = mapped_column(default=False)
    price: Mapped[float] = mapped_column(Float)
    old_price: Mapped[float | None] = mapped_column(Float)
    coupon: Mapped[str | None] = mapped_column(String(100))
    payment: Mapped[str | None] = mapped_column(Text)  # condição de pagamento lida na página (PIX/parcelas)
    image_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|rejected|pending|posted|failed
    reason: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(String(10), default="tech", server_default="tech", index=True)  # tech | lar (14/10/2026)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class SourceHealth(Base):
    __tablename__ = "source_health"
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_ok: Mapped[datetime | None] = mapped_column(UTCDateTime)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON)


class Coupon(Base):
    __tablename__ = "coupons"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    store: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(String(50))  # ML: sem código (ativação na conta)
    min_purchase: Mapped[float | None] = mapped_column(Float)
    max_discount: Mapped[float | None] = mapped_column(Float)
    expires_text: Mapped[str | None] = mapped_column(String(100))
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


def init_db() -> None:
    Base.metadata.create_all(engine)
    from app import pricehist
    with engine.begin() as conn:
        pricehist.criar(conn)
    # migrações leves para tabelas já existentes
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(offers)"))}
            if "canal" not in cols:
                conn.execute(text("ALTER TABLE offers ADD COLUMN canal VARCHAR(10) NOT NULL DEFAULT 'tech'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_offers_canal ON offers (canal)"))
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE offers ADD COLUMN IF NOT EXISTS product_key VARCHAR(64)"))
            conn.execute(text("ALTER TABLE offers ADD COLUMN IF NOT EXISTS score FLOAT DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_offers_product_key ON offers (product_key)"))
            conn.execute(text("ALTER TABLE offers ADD COLUMN IF NOT EXISTS payment TEXT"))
            conn.execute(text("ALTER TABLE offers ADD COLUMN IF NOT EXISTS post_title TEXT"))
