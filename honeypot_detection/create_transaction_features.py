import argparse

import numpy as np

from honeypot_detection.database.contract import Contract
from honeypot_detection.database.transaction import NormalTransaction, InternalTransaction
from honeypot_detection.multiprocess_by_address import multiprocess_by_address, Worker
from honeypot_detection.utils import address_list_from_file


COLUMNS = [
    "contract_address",
    "normal_transaction_count",
    "normal_transaction_block_count",
    "normal_transaction_before_creation_count",
    "normal_transaction_from_other_count",
    "normal_transaction_first_block",
    "normal_transaction_last_block",
    "normal_transaction_block_span",
    "normal_transaction_other_sender_count",
    "normal_transaction_count_per_block_mean",
    "normal_transaction_count_per_block_std",
    "normal_transaction_value_mean",
    "normal_transaction_value_std",
    "normal_transaction_gas_mean",
    "normal_transaction_gas_std",
    "normal_transaction_gas_used_mean",
    "normal_transaction_gas_used_std",
    "normal_transaction_time_delta_mean",
    "normal_transaction_time_delta_std",
    "normal_transaction_block_delta_mean",
    "normal_transaction_block_delta_std",
    "internal_transaction_count",
    "internal_transaction_block_count",
    "internal_transaction_creation_count",
    "internal_transaction_from_other_count",
    "internal_transaction_to_other_count",
    "internal_transaction_other_sender_count",
    "internal_transaction_other_receiver_count",
    "internal_transaction_count_per_block_mean",
    "internal_transaction_count_per_block_std",
    "internal_transaction_value_mean",
    "internal_transaction_value_std",
    "internal_transaction_gas_mean",
    "internal_transaction_gas_std",
    "internal_transaction_gas_used_mean",
    "internal_transaction_gas_used_std",
]


class TransactionFeatureWorker(Worker):

    def process_address(self, address):
        features = {"contract_address": address}
        contract = self.sqlalchemy_session.query(Contract).filter(Contract.address == address).one()

        internal_transactions = self._build_normal_transaction_features(contract, features)
        self._build_internal_transaction_features(contract, features, internal_transactions)

        self.send_output(features)

    def _build_normal_transaction_features(self, contract, features):
        transactions = self.sqlalchemy_session.query(NormalTransaction). \
            filter(NormalTransaction.crawled_from == contract.address). \
            order_by(NormalTransaction.block_number.desc(),
                     NormalTransaction.transaction_index.desc()).yield_per(self.yield_per)

        features["normal_transaction_count"] = 0
        features["normal_transaction_block_count"] = 0
        features["normal_transaction_before_creation_count"] = 0
        features["normal_transaction_from_other_count"] = 0

        last_block = None
        last_block_count = 0
        count_per_block = []
        other_senders = set()
        values = []
        gas = []
        gas_used = []
        last_timestamp = None
        time_deltas = []
        block_deltas = []
        contract_created = False
        children = []

        for transaction in transactions:
            # transactions should always have source
            assert transaction.source is not None, transaction.hash
            # transaction is not sent and received by the same party
            assert transaction.source != transaction.target, transaction.hash

            features["normal_transaction_count"] += 1

            # creation transaction
            if transaction.target is None:
                # there should be only one creation transaction
                assert not contract_created, transaction.hash
                # this was the creation transaction
                contract_created = True

                # in the creation transaction the creator is the source
                assert transaction.source == contract.creator, transaction.hash
                # the contract address added by me should match
                assert transaction.crawled_from == contract.address, transaction.hash

            # other transaction
            else:
                # non-creation transactions have no contract address
                assert transaction.contract_address is None, transaction.hash
                # only the one added by me
                assert transaction.crawled_from == contract.address, transaction.hash
                # the contract is always the target
                assert transaction.target == contract.address

                # this was before the creation transaction
                if not contract_created:
                    features["normal_transaction_before_creation_count"] += 1

            # first or new block
            if last_block is None or transaction.block_number != last_block:
                # new block
                if last_block is not None and last_block_count > 0:
                    count_per_block.append(last_block_count)
                    last_block_count = 0

                # count block
                features["normal_transaction_block_count"] += 1

            # count transaction
            last_block_count += 1

            # the creator is the source
            if transaction.source != contract.creator:
                other_senders.add(transaction.source)
                features["normal_transaction_from_other_count"] += 1

            # only count eth movement if there is no error
            if not transaction.is_error:
                values.append(transaction.value)
            gas.append(transaction.gas)
            gas_used.append(transaction.gas_used)

            # time delta
            if last_timestamp is not None:
                time_deltas.append(transaction.timestamp - last_timestamp)
            # update timestamp
            last_timestamp = transaction.timestamp

            # block delta
            if last_block is not None:
                block_deltas.append(transaction.block_number - last_block)
            # first block
            else:
                features["normal_transaction_first_block"] = transaction.block_number
            # update block
            last_block = transaction.block_number

            # append all the children from this transaction
            children.extend(self._fetch_transaction_children(transaction))

        # last block
        if last_block is not None and last_block_count > 0:
            count_per_block.append(last_block_count)

            features["normal_transaction_last_block"] = last_block
            features["normal_transaction_block_span"] = last_block - features["normal_transaction_first_block"]
        else:
            features["normal_transaction_last_block"] = features["normal_transaction_first_block"]
            features["normal_transaction_block_span"] = 0

        # aggregate features
        features["normal_transaction_other_sender_count"] = len(other_senders)

        self._aggregate(features, "normal_transaction_count_per_block", count_per_block)
        self._aggregate(features, "normal_transaction_value", values)
        self._aggregate(features, "normal_transaction_gas", gas)
        self._aggregate(features, "normal_transaction_gas_used", gas_used)
        self._aggregate(features, "normal_transaction_time_delta", time_deltas)
        self._aggregate(features, "normal_transaction_block_delta", block_deltas)

        # return the internal transactions ordered by normal transactions
        return children

    def _build_internal_transaction_features(self, contract, features, transactions):
        features["internal_transaction_count"] = 0
        features["internal_transaction_block_count"] = 0
        features["internal_transaction_creation_count"] = 0
        features["internal_transaction_from_other_count"] = 0
        features["internal_transaction_to_other_count"] = 0

        last_block = None
        last_block_count = 0
        count_per_block = []
        other_senders = set()
        other_receivers = set()
        values = []
        gas = []
        gas_used = []

        for transaction in transactions:
            # transactions should always have source
            assert transaction.source is not None, transaction.hash

            features["internal_transaction_count"] += 1

            # other contract creation
            if transaction.target is None:
                # the source is the contract that created this transaction
                assert transaction.source == transaction.crawled_from, transaction.hash
                # the new contract should not be the contract that created this transaction
                assert transaction.contract_address != transaction.crawled_from, transaction.hash
                # creation features
                features["internal_transaction_creation_count"] += 1
            # no other contract is created
            else:
                # non-creation transactions have no contract address
                assert transaction.contract_address is None, transaction.hash

                # IMPORTANT: _contract_address can be != contract["address"]
                # children from a transaction can be from another contract

            # first or new block
            if last_block is None or transaction.block_number != last_block:
                # new block
                if last_block is not None and last_block_count > 0:
                    count_per_block.append(last_block_count)
                    last_block_count = 0

                # count block
                features["internal_transaction_block_count"] += 1

            # count transaction
            last_block_count += 1

            # from other
            if transaction.source not in [contract.address, contract.creator]:
                other_senders.add(transaction.source)
                features["internal_transaction_from_other_count"] += 1

            # to other
            if transaction.target not in [contract.address, contract.creator]:
                other_receivers.add(transaction.target)
                features["internal_transaction_to_other_count"] += 1

            # update block
            last_block = transaction.block_number

            # only count eth movement if there is no error
            if not transaction.is_error:
                values.append(transaction.value)
            gas.append(transaction.gas)
            gas_used.append(transaction.gas_used)

        # last block
        if last_block is not None and last_block_count > 0:
            count_per_block.append(last_block_count)

        # aggregate features
        features["internal_transaction_other_sender_count"] = len(other_senders)
        features["internal_transaction_other_receiver_count"] = len(other_receivers)

        self._aggregate(features, "internal_transaction_count_per_block", count_per_block)
        self._aggregate(features, "internal_transaction_value", values)
        self._aggregate(features, "internal_transaction_gas", gas)
        self._aggregate(features, "internal_transaction_gas_used", gas_used)

    @staticmethod
    def _aggregate(features, name, values):
        if len(values) > 0:
            features[name + "_mean"] = np.mean(values)
            features[name + "_std"] = np.std(values)

    def _fetch_transaction_children(self, transaction):
        children = self.sqlalchemy_session.query(InternalTransaction).\
            filter(InternalTransaction.hash == transaction.hash).all()

        return list(children)


def main():
    argument_parser = argparse.ArgumentParser(description="Create features per contract.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to crawl, one address per line.")

    argument_parser.add_argument("output", type=str, help="Output file in csv format.")

    argument_parser.add_argument("--processes", type=int, help="Number of processes. Default is cpu_count() - 1.")
    argument_parser.add_argument("--yield_per", type=int, default=10, help="How many rows should be fetched at a time.")
    argument_parser.add_argument("--log_every", type=int, default=5, help="How many seconds between count logs.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    multiprocess_by_address(addresses,
                            TransactionFeatureWorker,
                            arguments.output,
                            COLUMNS,
                            num_processes=arguments.processes,
                            yield_per=arguments.yield_per,
                            log_every=arguments.log_every)


if __name__ == '__main__':
    main()
