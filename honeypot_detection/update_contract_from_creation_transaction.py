import logging

from honeypot_detection import config
from honeypot_detection.database.contract import Contract
from honeypot_detection.database.transaction import NormalTransaction, InternalTransaction

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


def main():
    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    contracts = sqlalchemy_session.query(Contract).all()

    for contract in contracts:
        transaction_internal = False

        # look for a normal transaction first
        creation_transaction = sqlalchemy_session.query(NormalTransaction).\
            filter(NormalTransaction.contract_address == contract.address).\
            one_or_none()

        # if there is no normal creation transaction
        if creation_transaction is None:
            transaction_internal = True

            # look for a internal transaction
            creation_transaction = sqlalchemy_session.query(InternalTransaction). \
                filter(InternalTransaction.contract_address == contract.address). \
                one_or_none()

            # something went wrong
            if creation_transaction is None:
                logger.warning("Contract {} has no creation transaction.".format(contract.address))
                continue

            # there is an internal creation transaction
            else:
                logger.debug("Contract {} was created with the internal transaction {:d}.".format(
                    contract.address, creation_transaction.sqlalchemy_id))

        # there is a normal creation transaction
        else:
            logger.debug("Contract {} was created with the normal transaction {}.".format(
                contract.address, creation_transaction.hash))

        # others
        contract.timestamp = creation_transaction.timestamp
        contract.creator = creation_transaction.source
        contract.block_number = creation_transaction.block_number
        contract.transaction_hash = creation_transaction.hash
        contract.transaction_internal = transaction_internal

        # update
        sqlalchemy_session.add(contract)
        sqlalchemy_session.commit()

        logger.info("Contract {} was updated.".format(contract.address))


if __name__ == '__main__':
    main()
