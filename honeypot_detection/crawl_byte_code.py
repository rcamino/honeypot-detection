import argparse
import hashlib
import logging

from honeypot_detection import config
from honeypot_detection.database.contract import Contract
from honeypot_detection.utils import address_list_from_file

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


class ByteCodeCrawler:

    def __init__(self, sqlalchemy_session, etherscan_client):
        self.sqlalchemy_session = sqlalchemy_session
        self.etherscan_client = etherscan_client

    def crawl(self, address, update):
        logger.info("Starting byte code crawl for address {}...".format(address))

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

        logger.info("Requesting contract byte code...")

        # send request
        byte_code = self.etherscan_client.get_contract_byte_code_by_address(address)

        # parse response
        contract.byte_code = byte_code
        contract.has_byte_code = (byte_code is not None) and (byte_code not in ["", "0x"])

        if contract.has_byte_code:
            contract.byte_code_hash = hashlib.sha256(byte_code.encode("utf-8")).hexdigest()

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
        description="Crawl Etherscan contract byte code. "
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

    crawler = ByteCodeCrawler(sqlalchemy_session, etherscan_client)

    logger.info("Crawling byte code for {:d} addresses...".format(len(addresses)))

    for address in addresses:
        try:
            crawler.crawl(address, arguments.update)
        # if something goes wrong, skip the address and continue
        except Exception:
            logger.exception("Error requesting transactions for address {}:".format(address))

    logger.info("Done crawling transactions.")


if __name__ == '__main__':
    main()
