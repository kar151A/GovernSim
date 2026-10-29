"""Relational ownership and foreign keys with versionable JSON domain payloads."""
from sqlalchemy import create_engine, event, ForeignKey, Integer, JSON, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_pragmas(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=30000')

SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Asset(Base):
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class Control(Base):
    __tablename__ = 'controls'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class Obligation(Base):
    __tablename__ = 'obligations'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class Evidence(Base):
    __tablename__ = 'evidence'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    control_id: Mapped[str] = mapped_column(ForeignKey('controls.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class Assessment(Base):
    __tablename__ = 'assessments'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class Decision(Base):
    __tablename__ = 'decisions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey('assessments.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class Review(Base):
    __tablename__ = 'reviews'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey('decisions.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class Scenario(Base):
    __tablename__ = 'scenarios'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class ChangeEvent(Base):
    __tablename__ = 'change_events'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class Mapping(Base):
    __tablename__ = 'mappings'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    previous_hash: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    canonical_payload: Mapped[str] = mapped_column(Text)


def init_db():
    Base.metadata.create_all(engine)
    # DB-level immutability protects against accidental application UPDATE/DELETE.
    # A database superuser can still replace history; export anchors externally.
    with engine.begin() as connection:
        for table in ('audit_events', 'reviews', 'decisions', 'assessments', 'evidence', 'evidence_attestations'):
            if engine.dialect.name == 'sqlite':
                for action in ('UPDATE', 'DELETE'):
                    connection.execute(text(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only record'); END"))
            else:
                connection.execute(text("CREATE OR REPLACE FUNCTION reject_history_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'append-only record'; END; $$ LANGUAGE plpgsql"))
                connection.execute(text(f'DROP TRIGGER IF EXISTS {table}_immutable ON {table}'))
                connection.execute(text(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()'))

class EvidenceAttestation(Base):
    __tablename__ = 'evidence_attestations'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey('evidence.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)
