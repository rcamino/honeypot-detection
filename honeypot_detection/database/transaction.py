from sqlalchemy import Column, Integer, String, Boolean, Float, Text, Index, BigInteger

from honeypot_detection.database.base import Base


class Transaction(Base):
    __abstract__ = True

    timestamp = Column(Integer)
    block_number = Column(Integer)
    source = Column(String(length=42))
    target = Column(String(length=42))
    value = Column(Float())
    gas = Column(Integer())
    gas_used = Column(Integer())
    is_error = Column(Boolean)
    contract_address = Column(String(length=42), index=True)
    crawled_from = Column(String(length=42))
    input = Column(Text())


class NormalTransaction(Transaction):
    __tablename__ = "normal_transactions"

    # index for the trace queries
    __table_args__ = (Index("ix_trace_queries", "crawled_from", "block_number", "transaction_index"),)

    hash = Column(String(length=66), primary_key=True, autoincrement=False)
    gas_price = Column(BigInteger)
    nonce = Column(String(length=128))
    confirmations = Column(Integer)
    tx_receipt_status = Column(Boolean)
    transaction_index = Column(Integer)
    cumulative_gas_used = Column(Integer())
    block_hash = Column(String(length=66))


class InternalTransaction(Transaction):
    __tablename__ = "internal_transactions"

    # internal transactions have no unique identifier, but the ORM does not like that, so I created some fake ID.
    sqlalchemy_id = Column(Integer, primary_key=True, autoincrement=True)
    # non unique, it is the hash of the parent normal transaction, but need to index for trace queries
    hash = Column(String(length=66), index=True)
