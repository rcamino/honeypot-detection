import argparse
import csv
import logging

from honeypot_detection import config  # just to define log level


logger = logging.getLogger(__name__)


ADDRESS_FIELD = "contract_address"


def main():
    argument_parser = argparse.ArgumentParser(description="Merge csv files by contract address.")

    argument_parser.add_argument("output", type=str, help="Output csv file.")
    argument_parser.add_argument("inputs", type=str, help="Input csv files.", nargs="+")

    arguments = argument_parser.parse_args()

    values_by_address = {}
    all_fields_in_order = []
    all_fields_set = set()
    first_file = True

    for i, input_file_path in enumerate(arguments.inputs, start=1):
        with open(input_file_path, "r") as csv_file:
            reader = csv.DictReader(csv_file)

            # get the fields from this file (but ignore the address because it will be duplicated)
            fields = []
            address_present = False
            for field in reader.fieldnames:
                # it is the address
                if field == ADDRESS_FIELD:
                    address_present = True
                # not the address
                else:
                    # check duplicates
                    assert field not in all_fields_set
                    # add the field everywhere
                    fields.append(field)
                    all_fields_in_order.append(field)
                    all_fields_set.add(field)

            logger.info("{:d} fields added from file {:d}/{:d}.".format(len(fields), i, len(arguments.inputs)))

            # verify that the address was in the field list of the file
            assert address_present

            # append the values to each contract
            for j, row in enumerate(reader, start=1):
                address = row[ADDRESS_FIELD]

                # if it is the first file the address needs to be defined
                if first_file:
                    assert address not in values_by_address
                    values_by_address[address] = []
                # the address should be defined, if not, the file rows don't match
                else:
                    assert address in values_by_address

                # append every value using the fixed field order
                for field in fields:
                    values_by_address[address].append(row[field])

                if j % 1000 == 0:
                    logger.info("{:d} rows read from file {:d}/{:d}.".format(j, i, len(arguments.inputs)))

            # first file already read
            first_file = False

        logger.info("{:d}/{:d} files merged.".format(i, len(arguments.inputs)))

    logger.info("Writing...")

    with open(arguments.output, "w") as csv_file:
        writer = csv.DictWriter(csv_file, [ADDRESS_FIELD] + all_fields_in_order)
        writer.writeheader()
        for i, (address, values) in enumerate(values_by_address.items(), start=1):
            row = {ADDRESS_FIELD: address}
            for field, value in zip(all_fields_in_order, values):
                row[field] = value
            writer.writerow(row)

            if i % 1000 == 0:
                logger.info("Writing {:d}/{:d}...".format(i, len(values_by_address)))

    logger.info("Done.")


if __name__ == '__main__':
    main()
