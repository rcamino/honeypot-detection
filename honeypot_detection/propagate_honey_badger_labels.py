import logging

from honeypot_detection import config
from honeypot_detection.database.contract import Contract
from honeypot_detection.database.honey_badger import HoneyBadgerContractLabel, HoneyBadgerNormalizedContractLabel

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


def main():
    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    # fetch all the normalized contract labels into memory
    norm_contract_labels = list(sqlalchemy_session.query(HoneyBadgerNormalizedContractLabel))
    norm_count = 0

    # iterate all the normalized contract labels
    for norm_contract_label in norm_contract_labels:
        # fetch the contract
        norm_contract = sqlalchemy_session.query(Contract).filter(Contract.address == norm_contract_label.address).\
            one_or_none()

        # check that the contract exists
        if norm_contract is None:
            logger.info("Contract {} was not found.".format(norm_contract_label.address))
            continue

        # check that the contract has byte code
        if not norm_contract.has_byte_code:
            logger.info("Contract {} has no byte code.".format(norm_contract_label.address))
            continue

        # fetch the contracts with the same byte code hash
        contracts = sqlalchemy_session.query(Contract).\
            filter(Contract.byte_code_hash == norm_contract.byte_code_hash)

        # iterate all the contracts with the same byte code hash
        de_norm_count = 0
        for contract in contracts:
            # create the de-normalized label
            contract_label = HoneyBadgerContractLabel(
                address=contract.address,
                honey_badger_label_id=norm_contract_label.honey_badger_label_id,
                evaluation_positive=norm_contract_label.evaluation_positive)

            sqlalchemy_session.add(contract_label)
            de_norm_count += 1

        # commit all the de-normalized labels for the current normalized label
        sqlalchemy_session.commit()
        norm_count += 1
        logger.info("Normalized label {:d}/{:d} propagated into {:d} de-normalized labels.".format(
            norm_count, len(norm_contract_labels), de_norm_count))


if __name__ == '__main__':
    main()
