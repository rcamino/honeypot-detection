import argparse

from operator import itemgetter

from honeypot_detection import config
from honeypot_detection.database.fund_flow_cases import FundFlowCase

from honeypot_detection.fund_flow_cases import FUND_FLOW_CASE_ID_BY_NAME

from sqlalchemy.orm import sessionmaker


def main():
    argument_parser = argparse.ArgumentParser(description="Load the case dictionary into the database.")
    arguments = argument_parser.parse_args()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    # validate unique values
    for (name, _id) in FUND_FLOW_CASE_ID_BY_NAME.items():
        for (other_name, other_id) in FUND_FLOW_CASE_ID_BY_NAME.items():
            assert name == other_name or _id != other_id

    # insert the database entries
    for name, _id in sorted(FUND_FLOW_CASE_ID_BY_NAME.items(), key=itemgetter(1)):
        sqlalchemy_session.add(FundFlowCase(id=_id, value=name))

    sqlalchemy_session.commit()


if __name__ == '__main__':
    main()
