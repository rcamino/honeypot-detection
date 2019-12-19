import argparse
import pickle

from honeypot_detection import config
from honeypot_detection.database.all_tables import find_model_by_table

from sqlalchemy.orm import sessionmaker


def load_dictionary(sqlalchemy_session, table, dictionary_file):
    model = find_model_by_table(table)
    if model is None:
        raise Exception("No model registered for table '{}'.".format(table))

    dictionary = pickle.load(dictionary_file)

    for entry_id, entry_value in dictionary["id_to_value"].items():
        entry = model(id=entry_id, value=entry_value)

        if "id_to_parent_id" in dictionary:
            entry.parent_id = dictionary["id_to_parent_id"][entry_id]

        sqlalchemy_session.add(entry)

    sqlalchemy_session.commit()


def main():
    argument_parser = argparse.ArgumentParser(description="Load dictionary from a file into the database.")

    argument_parser.add_argument("dictionary", type=argparse.FileType("rb"),
                                 help="Input dictionary file in pickle format.")

    argument_parser.add_argument("table", type=str, help="Database table name.")

    arguments = argument_parser.parse_args()

    sqlalchemy_engine = config.create_sqlalchemy_engine()
    sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

    load_dictionary(sqlalchemy_session, arguments.table, arguments.dictionary)


if __name__ == '__main__':
    main()
