from sqlalchemy import Column, String, Integer, Boolean

from honeypot_detection.database.base import Base
from honeypot_detection.database.dictionary import Dictionary


class HoneyBadgerLabel(Dictionary):
    __tablename__ = "honey_badger_labels"


class HoneyBadgerNormalizedContractLabel(Base):
    __tablename__ = "honey_badger_normalized_contract_labels"

    address = Column(String(length=42), primary_key=True, autoincrement=False)  # fixed size
    honey_badger_label_id = Column(Integer())
    evaluation_positive = Column(Boolean())


class HoneyBadgerContractLabel(Base):
    __tablename__ = "honey_badger_contract_labels"

    address = Column(String(length=42), primary_key=True, autoincrement=False)  # fixed size
    honey_badger_label_id = Column(Integer())
    evaluation_positive = Column(Boolean())
