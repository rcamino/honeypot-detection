import argparse
import logging

from honeypot_detection import config
from honeypot_detection.database.transaction import NormalTransaction, InternalTransaction
from honeypot_detection.database.transaction_crawl import NormalTransactionCrawl, InternalTransactionCrawl
from honeypot_detection.utils import address_list_from_file

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


class TransactionCrawler:

    def __init__(self, sqlalchemy_session, etherscan_client):
        self.sqlalchemy_session = sqlalchemy_session
        self.etherscan_client = etherscan_client

    def crawl(self, address, max_requests=None, size=None):
        normal_transaction_crawl = self._crawl_of_type(address,
                                                       self.etherscan_client.TRANSACTION_TYPE_NORMAL,
                                                       NormalTransactionCrawl,
                                                       max_requests=max_requests,
                                                       size=size)

        internal_transaction_crawl = self._crawl_of_type(address,
                                                         self.etherscan_client.TRANSACTION_TYPE_INTERNAL,
                                                         InternalTransactionCrawl,
                                                         max_requests=max_requests,
                                                         size=size)

        return normal_transaction_crawl, internal_transaction_crawl

    def _crawl_of_type(self, address, transaction_type, transaction_crawl_model, max_requests=None, size=None):
        logger.info("Starting transaction crawl: address={} type={}".format(address, transaction_type))

        # first fetch the crawl information for the address and transaction type
        transaction_crawl = self.sqlalchemy_session.query(transaction_crawl_model).\
            filter(transaction_crawl_model.address == address).one_or_none()

        if transaction_crawl is None:
            transaction_crawl = transaction_crawl_model(address=address, finished=False, count=0, last_block=0)
            self.sqlalchemy_session.add(transaction_crawl)
            self.sqlalchemy_session.commit()

        # check if the crawl already finished
        if transaction_crawl.finished:
            logger.info("Crawl already finished with {:d} transactions until block {:d}.".format(
                transaction_crawl.count, transaction_crawl.last_block))
            return transaction_crawl

        # check if the crawl already started
        if transaction_crawl.last_block > 0:
            start_block = transaction_crawl.last_block + 1
            logger.info("{:d} transactions were crawled until block {:d}, continuing from block {:d}.".format(
                transaction_crawl.count, transaction_crawl.last_block, start_block
            ))
        # the crawl didn't start yet
        else:
            start_block = 0
            logger.info("0 transactions were crawled, starting from block 0.")

        # keep asking for more blocks
        inserted_count = 0
        request_count = 0
        keep_requesting = True
        while keep_requesting and (max_requests is None or request_count < max_requests):
            logger.info("Requesting transactions: start_block={:d}".format(start_block))

            # send request
            responses = self.etherscan_client.list_transactions_by_address(address,
                                                                           transaction_type,
                                                                           start_block=start_block,
                                                                           offset=size)

            # parse responses
            transactions = [self._parse_response(address, transaction_type, response)
                            for response in responses]

            request_count += 1

            # if there are results we need to insert the transactions and update the crawl
            # and check if it is necessary to continue crawling
            if len(transactions) > 0:
                logger.info("{:d} transactions received.".format(len(transactions)))

                # transaction block numbers in ascending order
                block_numbers = sorted([transaction.block_number for transaction in transactions])
                last_block_number = block_numbers[-1]

                # if the page is full we need to continue crawling just in case there are more transactions
                if len(transactions) >= self.etherscan_client.REQUEST_LIMIT:
                    # we need to discard the transactions from the last block
                    # in case that there are more transactions on that block
                    previous_length = len(transactions)

                    transactions = [transaction for transaction in transactions
                                    if transaction.block_number != last_block_number]

                    logger.info("{:d} transactions discarded from last block.".format(
                        previous_length - len(transactions)))
                    # and we continue the crawl on the block we just discarded
                    start_block = last_block_number
                    keep_requesting = True
                    last_block_number = block_numbers[-2]

                # if the page is not full, it was the last page
                else:
                    transaction_crawl.finished = True
                    keep_requesting = False

                # insert the transactions and update the crawl
                self.sqlalchemy_session.add_all(transactions)
                transaction_crawl.count += len(transactions)
                transaction_crawl.last_block = last_block_number
                self.sqlalchemy_session.add(transaction_crawl)
                self.sqlalchemy_session.commit()
                logger.info("{:d} transactions inserted.".format(len(transactions)))
                inserted_count += len(transactions)

            # if there are no results we finished the crawl
            else:
                transaction_crawl.finished = True
                self.sqlalchemy_session.add(transaction_crawl)
                self.sqlalchemy_session.commit()
                logger.info("No more transactions inserted.")
                keep_requesting = False

        logger.info("{:d} total transactions inserted.".format(inserted_count))

        return transaction_crawl

    def _parse_response(self, address, transaction_type, response):
        # normal transaction fields
        if transaction_type == self.etherscan_client.TRANSACTION_TYPE_NORMAL:
            transaction = NormalTransaction()
            transaction.gas_price = self.etherscan_client.parse_int(response["gasPrice"])
            transaction.nonce = self.etherscan_client.parse_int(response["nonce"])
            transaction.confirmations = self.etherscan_client.parse_int(response["confirmations"])
            transaction.tx_receipt_status = self.etherscan_client.parse_bool(response["txreceipt_status"])
            transaction.transaction_index = self.etherscan_client.parse_int(response["transactionIndex"])
            transaction.cumulative_gas_used = self.etherscan_client.parse_int(response["cumulativeGasUsed"])
            transaction.block_hash = self.etherscan_client.parse_str(response["blockHash"])
        # internal transaction fields
        elif transaction_type == self.etherscan_client.TRANSACTION_TYPE_INTERNAL:
            transaction = InternalTransaction()

        # common fields
        transaction.timestamp = self.etherscan_client.parse_int(response["timeStamp"])
        transaction.block_number = self.etherscan_client.parse_int(response["blockNumber"])
        transaction.source = self.etherscan_client.parse_str(response["from"])
        transaction.target = self.etherscan_client.parse_str(response["to"])  # sometimes empty
        transaction.hash = self.etherscan_client.parse_str(response["hash"])
        transaction.value = self.etherscan_client.parse_value(response["value"])
        transaction.gas = self.etherscan_client.parse_int(response["gas"])
        transaction.gas_used = self.etherscan_client.parse_int(response["gasUsed"])
        transaction.is_error = self.etherscan_client.parse_bool(response["isError"])
        transaction.contract_address = self.etherscan_client.parse_str(response["contractAddress"])  # sometimes empty
        transaction.input = self.etherscan_client.parse_str(response["input"])

        # added fields
        transaction.crawled_from = address

        return transaction


def main():
    argument_parser = argparse.ArgumentParser(
        description="Crawl Etherscan contract transactions. "
                    + "No more than one process or thread should be used for the same contract.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to crawl, one address per line.")

    argument_parser.add_argument("--max_requests", type=int,
                                 help="Maximum number of requests per address on each iteration (horizontal crawl).")

    argument_parser.add_argument("--max_iterations", type=int, default=0,
                                 help="Maximum number of iterations (horizontal crawl).")

    argument_parser.add_argument("--size", type=int, help="Number of transactions per response.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    etherscan_client = config.create_etherscan_client()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    crawler = TransactionCrawler(sqlalchemy_session, etherscan_client)

    logger.info("Crawling transactions for {:d} addresses...".format(len(addresses)))

    # while there are addresses to crawl
    i = 0
    while len(addresses) > 0 and (arguments.max_iterations == 0 or i < arguments.max_iterations):
        remaining_addresses = []
        for address in addresses:
            try:
                transaction_crawls = crawler.crawl(address,
                                                   max_requests=arguments.max_requests,
                                                   size=arguments.size)

                # check if there are remaining transactions for this address
                normal_transaction_crawl, internal_transaction_crawl = transaction_crawls
                if not normal_transaction_crawl.finished or not internal_transaction_crawl.finished:
                    remaining_addresses.append(address)

            # if something goes wrong, skip the address and continue
            except Exception:
                logger.exception("Error requesting transactions for address {}:".format(address))

        # if the crawl is not horizontal, do not continue
        if arguments.max_requests is None:
            addresses = []
        # if the crawl is horizontal, continue with the remaining addresses
        else:
            addresses = remaining_addresses

        # next iteration
        i += 1

    logger.info("Done crawling transactions.")


if __name__ == '__main__':
    main()
