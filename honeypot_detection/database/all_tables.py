from honeypot_detection.database.contract import Contract
from honeypot_detection.database.contract_compiler_version import ContractCompilerMajorVersion,\
    ContractCompilerMinorVersion, ContractCompilerPatchVersion
from honeypot_detection.database.contract_library import ContractLibrary
from honeypot_detection.database.fund_flow_cases import FundFlowCase
from honeypot_detection.database.honey_badger import HoneyBadgerLabel, HoneyBadgerNormalizedContractLabel
from honeypot_detection.database.transaction import NormalTransaction, InternalTransaction
from honeypot_detection.database.transaction_crawl import NormalTransactionCrawl, InternalTransactionCrawl
from honeypot_detection.database.base import Base


def find_model_by_table(table):
    for model in Base._decl_class_registry.values():
        if hasattr(model, '__tablename__') and model.__tablename__ == table:
            return model
    return None
