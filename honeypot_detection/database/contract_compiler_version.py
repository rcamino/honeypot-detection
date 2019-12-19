from sqlalchemy import Column, Integer

from honeypot_detection.database.dictionary import Dictionary


class ContractCompilerMajorVersion(Dictionary):
    __tablename__ = "contract_compiler_major_versions"


class ContractCompilerMinorVersion(Dictionary):
    __tablename__ = "contract_compiler_minor_versions"
    parent_id = Column(Integer(), index=True)


class ContractCompilerPatchVersion(Dictionary):
    __tablename__ = "contract_compiler_patch_versions"
    parent_id = Column(Integer(), index=True)
