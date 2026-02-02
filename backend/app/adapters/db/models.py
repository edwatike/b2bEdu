"""SQLAlchemy database models."""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, BigInteger, Text, Date, JSON,
    ForeignKey, UniqueConstraint, Index, LargeBinary
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class ModeratorSupplierModel(Base):
    """Model for moderator suppliers table."""
    __tablename__ = "moderator_suppliers"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Basic fields
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="supplier")
    
    # Checko requisites
    ogrn: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    kpp: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    okpo: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    company_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    legal_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Checko contacts
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Financial data
    authorized_capital: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    profit: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    finance_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Legal cases
    legal_cases_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    legal_cases_sum: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    legal_cases_as_plaintiff: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    legal_cases_as_defendant: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Full Checko data (compressed JSON, gzip)
    checko_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    keywords: Mapped[list["SupplierKeywordModel"]] = relationship(
        "SupplierKeywordModel",
        back_populates="supplier",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_suppliers_inn", "inn"),
        Index("idx_suppliers_domain", "domain"),
        Index("idx_suppliers_type", "type"),
    )


class KeywordModel(Base):
    """Model for keywords table."""
    __tablename__ = "keywords"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    suppliers: Mapped[list["SupplierKeywordModel"]] = relationship(
        "SupplierKeywordModel",
        back_populates="keyword"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_keywords_keyword", "keyword"),
    )


class SupplierKeywordModel(Base):
    """Model for supplier_keywords junction table."""
    __tablename__ = "supplier_keywords"
    
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("moderator_suppliers.id", ondelete="CASCADE"),
        primary_key=True
    )
    keyword_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True
    )
    url_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parsing_run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    supplier: Mapped["ModeratorSupplierModel"] = relationship(
        "ModeratorSupplierModel",
        back_populates="keywords"
    )
    keyword: Mapped["KeywordModel"] = relationship(
        "KeywordModel",
        back_populates="suppliers"
    )


class BlacklistModel(Base):
    """Model for blacklist table."""
    __tablename__ = "blacklist"
    
    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    parsing_run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_blacklist_domain", "domain"),
    )


class ParsingRequestModel(Base):
    """Model for parsing_requests table."""
    __tablename__ = "parsing_requests"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_keys_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    depth: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class ParsingRunModel(Base):
    """Model for parsing_runs table."""
    __tablename__ = "parsing_runs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("parsing_requests.id", ondelete="CASCADE"), nullable=False)
    parser_task_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    depth: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    results_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    process_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON object with parsing process details
    
    # Relationship
    request: Mapped[Optional["ParsingRequestModel"]] = relationship("ParsingRequestModel", lazy="select")
    
    # Indexes
    __table_args__ = (
        Index("idx_parsing_runs_status", "status"),
        Index("idx_parsing_runs_run_id", "run_id"),
    )


class DomainQueueModel(Base):
    """Model for domains_queue table."""
    __tablename__ = "domains_queue"
    
    # Primary key changed from domain to id to allow same domain for different keywords
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    parsing_run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default="google")  # google, yandex, or both
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"
    )  # pending, processing, completed, failed
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    # Indexes and unique constraint
    # IMPORTANT: Same domain can appear for different keywords and parsing runs
    # Unique constraint ensures no duplicates for (domain, keyword, parsing_run_id)
    __table_args__ = (
        Index("idx_domains_queue_status", "status"),
        Index("idx_domains_queue_keyword", "keyword"),
        Index("idx_domains_queue_parsing_run_id", "parsing_run_id"),
        Index("idx_domains_queue_domain_keyword", "domain", "keyword"),
        UniqueConstraint("domain", "keyword", "parsing_run_id", name="uq_domains_queue_domain_keyword_run"),
    )


class AuditLogModel(Base):
    """Model for audit_log table."""
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)  # INSERT, UPDATE, DELETE
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    old_data: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSONB as Text for now
    new_data: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSONB as Text for now
    changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_log_table_name", "table_name"),
        Index("idx_audit_log_operation", "operation"),
        Index("idx_audit_log_record_id", "record_id"),
        Index("idx_audit_log_changed_at", "changed_at"),
    )
