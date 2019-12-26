import argparse
import os
import pickle

from honeypot_detection import config

from sqlalchemy.orm import sessionmaker

from honeypot_detection.database.contract_compiler_version import ContractCompilerMajorVersion
from honeypot_detection.database.contract_compiler_version import ContractCompilerMinorVersion
from honeypot_detection.database.contract_compiler_version import ContractCompilerPatchVersion
from honeypot_detection.database.contract_library import ContractLibrary
from honeypot_detection.database.honey_badger import HoneyBadgerLabel
from honeypot_detection.fund_flow_cases import build_fund_flow_cases


class DictionaryFactory:

    def create(self):
        raise NotImplementedError


class DatabaseFactory(DictionaryFactory):

    def __init__(self, model):
        self.model = model

    def create(self):
        sqlalchemy_engine = config.create_sqlalchemy_engine()
        sqlalchemy_session = sessionmaker(bind=sqlalchemy_engine)()

        value_to_id = dict()
        for entry in sqlalchemy_session.query(self.model).all():
            value_to_id[entry.value] = entry.id

        sqlalchemy_session.close()
        sqlalchemy_engine.dispose()

        return value_to_id


class FundFlowCaseFactory(DictionaryFactory):

    def create(self):
        return build_fund_flow_cases()


FACTORIES = {
    "contract_compiler_major_versions": DatabaseFactory(ContractCompilerMajorVersion),
    "contract_compiler_minor_versions": DatabaseFactory(ContractCompilerMinorVersion),
    "contract_compiler_patch_versions": DatabaseFactory(ContractCompilerPatchVersion),
    "contract_libraries": DatabaseFactory(ContractLibrary),
    "honey_badger_labels": DatabaseFactory(HoneyBadgerLabel),
    "fund_flow_cases": FundFlowCaseFactory(),
}


def main():
    argument_parser = argparse.ArgumentParser(description="Dump propagated honey badger labels into a csv file.")

    argument_parser.add_argument("--dictionary", type=str, choices=FACTORIES.keys(),
                                 help="Name of the dictionary to dump. If not defined, all of them will be dumped.")

    argument_parser.add_argument("output", type=str,
                                 help="Output path. Should be a directory when no dictionary is defined,"
                                      + " or a pickle file for a specific dictionary.")

    arguments = argument_parser.parse_args()

    dictionary_by_path = {}

    if arguments.dictionary is None:
        for name, factory in FACTORIES.items():
            file_path = os.path.join(arguments.output, name + ".pickle")
            dictionary_by_path[file_path] = factory.create()
    else:
        dictionary_by_path[arguments.output] = FACTORIES[arguments.dictionary].create()

    for file_path, value_to_id in dictionary_by_path.items():
        dictionary = {"value_to_id": value_to_id, "id_to_value": {}}
        for value, _id in value_to_id.items():
            dictionary["id_to_value"][_id] = value

        with open(file_path, "wb") as dictionary_file:
            pickle.dump(dictionary, dictionary_file)


if __name__ == '__main__':
    main()
