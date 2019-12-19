from sqlalchemy import Column, Integer, Text

from honeypot_detection.database.base import Base


class Dictionary(Base):
    __abstract__ = True

    id = Column(Integer(), primary_key=True, autoincrement=True)
    value = Column(Text, nullable=False)
