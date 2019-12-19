from sqlalchemy import Column, Integer, String, Boolean

from honeypot_detection.database.base import Base


class TransactionCrawl(Base):
    __abstract__ = True

    address = Column(String(length=42), primary_key=True, autoincrement=False)
    finished = Column(Boolean, nullable=False, default=False)
    count = Column(Integer, nullable=False, default=0)
    last_block = Column(Integer, nullable=False, default=0)


class NormalTransactionCrawl(TransactionCrawl):
    __tablename__ = "normal_transaction_crawl"


class InternalTransactionCrawl(TransactionCrawl):
    __tablename__ = "internal_transaction_crawl"
