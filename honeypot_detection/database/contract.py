from sqlalchemy import Column, String, Integer, Boolean, Text

from honeypot_detection.database.base import Base


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    # crawled from source code
    address = Column(String(length=42), primary_key=True, autoincrement=False)  # fixed size
    name = Column(String(length=256))  # not sure about the size
    compiler_optimization = Column(Boolean())
    compiler_runs = Column(Integer())
    abi = Column(Text())
    license_type = Column(String(length=64))  # not sure about the size
    swarm_source = Column(String(length=128))  # not sure about the size
    source_code = Column(Text(length=2097152))  # had to extend this to be 2MB > TEXT=64KB

    # computed from creation transaction
    timestamp = Column(Integer())
    creator = Column(String(length=42))  # fixed size
    block_number = Column(Integer())
    transaction_hash = Column(String(length=66))  # fixed size
    transaction_internal = Column(Boolean())

    # computed from source code
    compiler_version_major_id = Column(Integer())
    compiler_version_minor_id = Column(Integer())
    compiler_version_patch_id = Column(Integer())
    library_id = Column(Integer())
    has_source_code = Column(Boolean())

    # computed from byte code
    byte_code = Column(Text())
    has_byte_code = Column(Boolean())
    byte_code_hash = Column(String(length=64), index=True)  # fixed size
