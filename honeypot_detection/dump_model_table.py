import argparse
import csv

from honeypot_detection import config
from honeypot_detection.database.all_tables import find_model_by_table

from sqlalchemy.orm import sessionmaker


def main():
    argument_parser = argparse.ArgumentParser(description="Dump a model table into a csv file.")

    argument_parser.add_argument("table", type=str, help="Model table name.")
    argument_parser.add_argument("output", type=argparse.FileType("w"), help="Output csv file.")
    argument_parser.add_argument("--yield_per", type=int, default=10, help="How many rows should be fetched at a time.")

    arguments = argument_parser.parse_args()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    model = find_model_by_table(arguments.table)
    columns = list([column.name for column in model.__table__.columns])

    csv_writer = csv.DictWriter(arguments.output, columns)
    csv_writer.writeheader()

    entries = sqlalchemy_session.query(model).yield_per(arguments.yield_per)

    for entry in entries:
        row = {}
        for column in columns:
            row[column] = getattr(entry, column)
        csv_writer.writerow(row)


if __name__ == '__main__':
    main()
