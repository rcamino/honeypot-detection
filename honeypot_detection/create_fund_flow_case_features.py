import argparse
import csv
import sys

from collections import Counter

from honeypot_detection.fund_flow_cases import FUND_FLOW_CASE_ID_BY_NAME


# for very long traces
csv.field_size_limit(sys.maxsize)


def fund_flow_case_field(_id):
    return "fund_flow_case_{:d}_frequency".format(_id)


def main():
    argument_parser = argparse.ArgumentParser(
        description="Create the fund flow case features from fund flow case sequences.")

    argument_parser.add_argument("input", type=str, help="Input file in csv format.")
    argument_parser.add_argument("output", type=str, help="Output file in csv format.")

    arguments = argument_parser.parse_args()

    number_of_fund_flow_cases = len(FUND_FLOW_CASE_ID_BY_NAME)

    # compute the fields
    fields = ["contract_address"]
    for _id in range(1, number_of_fund_flow_cases + 1):
        fields.append(fund_flow_case_field(_id))

    print("Start...")

    input_file = open(arguments.input, "r")
    output_file = open(arguments.output, "w")

    reader = csv.DictReader(input_file)
    writer = csv.DictWriter(output_file, fieldnames=fields)

    writer.writeheader()

    for i, input_row in enumerate(reader):
        # transform the value from bytes to a list of ints
        fund_flow_case_sequence = list(input_row["value"].encode("utf-8"))

        output_row = {"contract_address": input_row["address"]}

        counter = Counter()
        for _id in fund_flow_case_sequence:
            assert 0 < _id <= number_of_fund_flow_cases
            counter[_id] += 1

        sequence_length = len(fund_flow_case_sequence)

        for _id in range(1, number_of_fund_flow_cases + 1):
            if sequence_length > 0:
                output_row[fund_flow_case_field(_id)] = counter[_id] / sequence_length
            else:
                output_row[fund_flow_case_field(_id)] = 0.0

        writer.writerow(output_row)

    input_file.close()
    output_file.close()

    print("Finished.")


if __name__ == '__main__':
    main()
