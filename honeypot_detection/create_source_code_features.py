import argparse

from honeypot_detection.database.contract import Contract
from honeypot_detection.multiprocess_by_address import multiprocess_by_address, Worker
from honeypot_detection.utils import address_list_from_file


COLUMNS = [
    "contract_address",
    "contract_has_source_code",
    "contract_has_byte_code",
    "contract_compiler_runs",
    "contract_num_source_code_lines",
    "contract_compiler_version_major_id",
    "contract_compiler_version_minor_id",
    "contract_compiler_version_patch_id",
    "contract_library_id",
]


class SourceCodeFeatureWorker(Worker):

    def process_address(self, address):
        features = {"contract_address": address}
        contract = self.sqlalchemy_session.query(Contract).filter(Contract.address == address).one()

        features["contract_has_source_code"] = contract.has_source_code
        features["contract_has_byte_code"] = contract.has_byte_code

        if features["contract_has_source_code"]:
            # use this feature only if there is source code
            features["contract_compiler_runs"] = contract.compiler_runs

            features["contract_num_source_code_lines"] = len(contract.source_code.split("\n"))
        else:
            # force no runs if there is no source code
            features["contract_compiler_runs"] = None

        features["contract_compiler_version_major_id"] = contract.compiler_version_major_id
        features["contract_compiler_version_minor_id"] = contract.compiler_version_minor_id
        features["contract_compiler_version_patch_id"] = contract.compiler_version_patch_id
        features["contract_library_id"] = contract.library_id

        self.send_output(features)


def main():
    argument_parser = argparse.ArgumentParser(description="Create features per contract.")

    argument_parser.add_argument("contracts", type=argparse.FileType("r"),
                                 help="File path containing contracts to crawl, one address per line.")

    argument_parser.add_argument("output", type=str, help="Output file in csv format.")

    argument_parser.add_argument("--processes", type=int, help="Number of processes. Default is cpu_count() - 1.")
    argument_parser.add_argument("--log_every", type=int, default=5, help="How many seconds between count logs.")

    arguments = argument_parser.parse_args()

    addresses = address_list_from_file(arguments.contracts)

    multiprocess_by_address(addresses,
                            SourceCodeFeatureWorker,
                            arguments.output,
                            COLUMNS,
                            num_processes=arguments.processes,
                            log_every=arguments.log_every)


if __name__ == '__main__':
    main()
