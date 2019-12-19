import argparse
import csv
import logging
import re
import os

from honeypot_detection import config
from honeypot_detection.database.honey_badger import HoneyBadgerLabel, HoneyBadgerNormalizedContractLabel

from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


LABEL_PATTERN = re.compile(r"HoneyBadger Evaluation - ([a-zA-Z ]+).csv")


def add_label(label, labels, sqlalchemy_session):
    label_id = len(labels) + 1  # starts with one
    labels.append(label)
    sqlalchemy_session.add(HoneyBadgerLabel(id=label_id, name=label))
    logger.info("Created label: {:d}={}".format(label_id, label))
    return label_id


def extract_label(csv_name):
    matches = LABEL_PATTERN.findall(csv_name)
    assert matches is not None
    assert len(matches) == 1
    return matches[0]


def load_evaluation_csv(csv_path):
    with open(csv_path, "r") as csv_file:
        csv_reader = csv.DictReader(csv_file)

        return [{
            "normalized_address": row["Address"],
            "evaluation_positive": row["Positive"] == "TRUE"
        } for row in csv_reader if row["Address"] != "" and row["Source Code"] == "Yes"]


def main():
    argument_parser = argparse.ArgumentParser(description="Load Honey Badger labels.")

    argument_parser.add_argument("directory", type=str, help="Honey Badger evaluation directory path.")

    arguments = argument_parser.parse_args()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    labels = []
    sqlalchemy_session.commit()

    for csv_name in sorted(os.listdir(arguments.directory)):
        csv_path = os.path.join(arguments.directory, csv_name)

        if os.path.isfile(csv_path):
            label = extract_label(csv_name)
            label_id = add_label(label, labels, sqlalchemy_session)

            count = 0
            for entry in load_evaluation_csv(csv_path):
                sqlalchemy_session.add(HoneyBadgerNormalizedContractLabel(
                    honey_badger_label_id=label_id,
                    address=entry["normalized_address"],
                    evaluation_positive=entry["evaluation_positive"],
                ))
                count += 1

            logger.info("{:d} contracts were labeled.".format(count))
            sqlalchemy_session.commit()


if __name__ == '__main__':
    main()
