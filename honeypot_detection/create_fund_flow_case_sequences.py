import argparse

from collections import Counter

from honeypot_detection.fund_flow_cases import FUND_FLOW_CASE_ID_BY_NAME, create_fund_flow_case_if_valid
from honeypot_detection.database.contract import Contract
from honeypot_detection.database.transaction import NormalTransaction, InternalTransaction
from honeypot_detection.multiprocess_by_address import multiprocess_by_address, Worker
from honeypot_detection.utils import address_list_from_file


BALANCE_TOLERANCE = 1e-6

COLUMNS = ["address", "value"]


class FundFlowCaseSequenceWorker(Worker):

    def process_address(self, address):
        # get the contract
        contract = self.sqlalchemy_session.query(Contract).filter(Contract.address == address).one()

        # process to get the sequence
        sequence = self._contract_sequence(contract)

        # transform sequence as bytes because some sequences are too long (and each id fits in one byte anyways)
        self.send_output({"address": address, "value": bytes(sequence)})

    def _contract_sequence(self, contract):
        sequence = []
        contract_created = False

        transactions = self.sqlalchemy_session.query(NormalTransaction). \
            filter(NormalTransaction.crawled_from == contract.address). \
            order_by(NormalTransaction.block_number.desc(),
                     NormalTransaction.transaction_index.desc()).yield_per(self.yield_per)

        for transaction in transactions:
            # transactions should always have source
            assert transaction.source is not None, transaction.hash
            # transaction is not sent and received by the same party
            assert transaction.source != transaction.target, transaction.hash

            # creation transaction
            if transaction.target is None:
                # there should be only one creation transaction
                assert not contract_created, transaction.hash
                # this was the creation transaction
                contract_created = True
                # create the case
                case = self._creation_transaction_case(contract, transaction)
            # other transaction
            else:
                # create the case
                case = self._normal_transaction_case(contract, transaction)

            # add the case id to the sequence
            sequence.append(FUND_FLOW_CASE_ID_BY_NAME[case])

        return sequence

    def _creation_transaction_case(self, contract, transaction):
        # in the creation transaction the creator is the source
        assert transaction.source == contract.creator, transaction.hash
        # the contract address added by me should match
        assert transaction.crawled_from == contract.address, transaction.hash

        # return the case if it is valid
        case_values = self._extract_case_values(contract, transaction, other_sender=False, creation=True)
        return create_fund_flow_case_if_valid(transaction, case_values)

    def _normal_transaction_case(self, contract, transaction):
        # non-creation transactions have no contract address
        assert transaction.contract_address is None, transaction.hash
        # only the one added by me
        assert transaction.crawled_from == contract.address, transaction.hash
        # the contract is always the target
        assert transaction.target == contract.address

        # the creator is the source
        if transaction.source == contract.creator:
            case_values = self._extract_case_values(contract, transaction, other_sender=False)

        # other is the source
        else:
            case_values = self._extract_case_values(contract, transaction, other_sender=True)

        # return the case if it is valid
        return create_fund_flow_case_if_valid(transaction, case_values)

    def _extract_case_values(self, contract, transaction, other_sender=False, creation=False):
        # initialize values (they might change afterwards)
        case_values = {
            "sender": ("other" if other_sender else "creator"),
            "error": transaction.is_error,
            "balance_creator": "unchanged",
            "balance_contract": "unchanged",
            "balance_other_positive": False,
            "balance_other_negative": False,
        }

        # case specific values
        if other_sender:
            case_values["balance_sender"] = "unchanged"
        else:
            case_values["creation"] = creation

        # initialize balances with transaction value movement (if present)
        balances = Counter()
        value = int(transaction.value)
        if value > 0:
            # the source can be either the creator or another account
            balances[transaction.source] = -value
            # the target is always the contract
            balances[contract.address] = value

        # internal transaction balances and errors
        children = self.sqlalchemy_session.query(InternalTransaction).\
            filter(InternalTransaction.hash == transaction.hash).all()

        for child in children:
            case_values["error"] = case_values["error"] or child.is_error
            balances.update(self._calculate_internal_transaction_balance(child))

        # update the values according to balances
        for address, value in balances.items():
            # separate balance into bins
            if abs(value) < BALANCE_TOLERANCE:  # check if very close to zero to avoid arithmetic errors
                value_bin = "unchanged"
            elif value > 0:
                value_bin = "positive"
            else:
                value_bin = "negative"

            # balance creator
            if address == contract.creator:
                case_values["balance_creator"] = value_bin

            # balance contract
            elif address == contract.address:
                case_values["balance_contract"] = value_bin

            # balance sender
            elif address == transaction.source:
                assert other_sender
                assert transaction.source != contract.creator
                case_values["balance_sender"] = value_bin

            # balance other
            else:
                # at least one other account has a positive balance
                if value_bin == "positive":
                    case_values["balance_other_positive"] = True

                # at least one other account has a negative balance
                if value_bin == "negative":
                    case_values["balance_other_negative"] = True

        return case_values

    @staticmethod
    def _calculate_internal_transaction_balance(transaction):
        # transactions should always have source
        assert transaction.source is not None, transaction.hash

        balance = Counter()
        value = int(transaction.value)

        # if value is moved
        if value > 0:
            # the source loses the value
            balance[transaction.source] = -value

            # creation transaction
            if transaction.target is None:
                # the source is the contract that created this transaction
                assert transaction.source == transaction.crawled_from, transaction.hash
                # the new contract should not be the contract that created this transaction
                assert transaction.contract_address != transaction.crawled_from, transaction.hash
                # the new contract gets the value
                balance[transaction.contract_address] = value
            # non-creation transaction
            else:
                # non-creation transactions have no contract address
                assert transaction.contract_address is None, transaction.hash

                # IMPORTANT: _contract_address can be != contract["address"]
                # children from a transaction can be from another contract

                # the target gets the value
                # the + should be used, or else transactions with same source and target will get a wrong balance
                balance[transaction.target] += value

        return balance


def main():
    argument_parser = argparse.ArgumentParser(description="Create fund flow case sequences per contract.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to calculate sequences, one address per line.")

    argument_parser.add_argument("output", type=str, help="Output file in csv format.")

    argument_parser.add_argument("--processes", type=int, help="Number of processes. Default is cpu_count() - 1.")
    argument_parser.add_argument("--yield_per", type=int, default=10, help="How many rows should be fetched at a time.")
    argument_parser.add_argument("--log_every", type=int, default=5, help="How many seconds between count logs.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    multiprocess_by_address(addresses,
                            FundFlowCaseSequenceWorker,
                            arguments.output,
                            COLUMNS,
                            num_processes=arguments.processes,
                            yield_per=arguments.yield_per,
                            log_every=arguments.log_every)


if __name__ == '__main__':
    main()
