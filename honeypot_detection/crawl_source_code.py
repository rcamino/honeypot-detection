import argparse
import logging
import re

from honeypot_detection import config
from honeypot_detection.database.contract import Contract
from honeypot_detection.database.contract_compiler_version import ContractCompilerMajorVersion
from honeypot_detection.database.contract_compiler_version import ContractCompilerMinorVersion
from honeypot_detection.database.contract_compiler_version import ContractCompilerPatchVersion
from honeypot_detection.database.contract_library import ContractLibrary
from honeypot_detection.utils import address_list_from_file

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


class SourceCodeCrawler:

    COMPILER_VERSION_PATTERN = re.compile(r"v([0-9]+)\.([0-9]+)\.(.+)")

    def __init__(self, sqlalchemy_session, etherscan_client):
        self.sqlalchemy_session = sqlalchemy_session
        self.etherscan_client = etherscan_client

    def split_compiler_version(self, compiler_version):
        matches = self.COMPILER_VERSION_PATTERN.findall(compiler_version)
        assert matches is not None and len(matches) == 1
        return matches[0]

    def fetch_or_create_dictionary_entry_id(self, value, model, parent_id=None):
        if value is None or value.strip() == "":
            return None

        query = self.sqlalchemy_session.query(model).filter(model.value == value)

        if parent_id is not None:
            query = query.filter(model.parent_id == parent_id)

        entry = query.one_or_none()

        # create the entry if it does not exist
        if entry is None:
            entry = model(value=value)

            if parent_id is not None:
                entry.parent_id = parent_id

            self.sqlalchemy_session.add(entry)
            self.sqlalchemy_session.flush()
            assert entry.id is not None

        return entry.id

    def crawl(self, address, update):
        logger.info("Starting source code crawl for address {}...".format(address))

        # first fetch the contract
        contract = self.sqlalchemy_session.query(Contract).filter(Contract.address == address).one_or_none()

        if contract is None:
            logger.info("Creating new contract...")
            contract = Contract(address=address)
        else:
            if update:
                logger.info("Contract already exists, updating...")
            else:
                logger.info("Contract already exists, aborting.")
                return contract

        logger.info("Requesting contract source code...")

        # send request
        response = self.etherscan_client.get_contract_source_code_by_address(address)

        # parse response
        contract.source_code = self.etherscan_client.parse_str(response["SourceCode"])
        contract.abi = self.etherscan_client.parse_str(response["ABI"])
        contract.name = self.etherscan_client.parse_str(response["ContractName"])
        contract.compiler_optimization = self.etherscan_client.parse_bool(response["OptimizationUsed"])
        contract.compiler_runs = self.etherscan_client.parse_int(response["Runs"])
        contract.license_type = self.etherscan_client.parse_str(response["LicenseType"])
        contract.swarm_source = self.etherscan_client.parse_str(response["SwarmSource"])

        # general properties calculated from the source code
        contract.has_source_code = (contract.source_code is not None) and (contract.source_code != "")

        # compiler version
        compiler_version = self.etherscan_client.parse_str(response["CompilerVersion"])
        if (compiler_version is not None) and (compiler_version != ""):
            compiler_version_major, compiler_version_minor, compiler_version_patch = \
                self.split_compiler_version(compiler_version)

            contract.compiler_version_major_id = self.fetch_or_create_dictionary_entry_id(
                compiler_version_major, ContractCompilerMajorVersion)

            contract.compiler_version_minor_id = self.fetch_or_create_dictionary_entry_id(
                compiler_version_minor, ContractCompilerMinorVersion, parent_id=contract.compiler_version_major_id)

            contract.compiler_version_patch_id = self.fetch_or_create_dictionary_entry_id(
                compiler_version_patch, ContractCompilerPatchVersion, parent_id=contract.compiler_version_minor_id)

        # library
        library = self.etherscan_client.parse_str(response["Library"])
        contract.library_id = self.fetch_or_create_dictionary_entry_id(library, ContractLibrary)

        # insert or update
        self.sqlalchemy_session.add(contract)
        self.sqlalchemy_session.commit()

        if update:
            logger.info("Contract updated.")
        else:
            logger.info("Contract inserted.")

        return contract


def main():
    argument_parser = argparse.ArgumentParser(
        description="Crawl Etherscan contract source code. "
                    + "No more than one process or thread should be used for the same contract.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to crawl, one address per line.")

    argument_parser.add_argument("--update", action="store_true", default=False,
                                 help="Update contract if exists. If not set, throw an error when the contract exists.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    etherscan_client = config.create_etherscan_client()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    crawler = SourceCodeCrawler(sqlalchemy_session, etherscan_client)

    logger.info("Crawling source code for {:d} addresses...".format(len(addresses)))

    for address in addresses:
        try:
            crawler.crawl(address, arguments.update)
        # if something goes wrong, skip the address and continue
        except Exception:
            logger.exception("Error requesting transactions for address {}:".format(address))

    logger.info("Done crawling transactions.")


if __name__ == '__main__':
    main()
