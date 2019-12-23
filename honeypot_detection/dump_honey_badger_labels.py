import argparse
import csv

from honeypot_detection import config
from honeypot_detection.database.honey_badger import HoneyBadgerLabel, HoneyBadgerContractLabel

from sqlalchemy.orm import sessionmaker

from honeypot_detection.utils import address_list_from_file


def main():
    argument_parser = argparse.ArgumentParser(description="Dump propagated honey badger labels into a csv file.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to label, one address per line.")

    argument_parser.add_argument("output", type=argparse.FileType("w"), help="Output csv file.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    csv_writer = csv.DictWriter(arguments.output, ["contract_address",
                                                   "contract_evaluation_positive",
                                                   "contract_label_id",
                                                   "contract_label_name"])

    csv_writer.writeheader()

    label_id_to_name = {}
    labels = sqlalchemy_session.query(HoneyBadgerLabel).all()
    for label in labels:
        label_id_to_name[label.id] = label.name

    for address in addresses:
        entry = sqlalchemy_session.query(HoneyBadgerContractLabel).\
            filter(HoneyBadgerContractLabel.address == address).one_or_none()

        if entry is None:
            csv_writer.writerow({"contract_address": address,
                                 "contract_evaluation_positive": 0,
                                 "contract_label_id": 0,
                                 "contract_label_name": "Not Honeypot"})
        else:
            csv_writer.writerow({"contract_address": address,
                                 "contract_evaluation_positive": entry.evaluation_positive,
                                 "contract_label_id": entry.honey_badger_label_id,
                                 "contract_label_name": label_id_to_name[entry.honey_badger_label_id]})


if __name__ == '__main__':
    main()
