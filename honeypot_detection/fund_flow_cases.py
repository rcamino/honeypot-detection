BOOLEAN_VALUES = [True, False]
BALANCE_VALUES = ["positive", "unchanged", "negative"]

FUND_FLOW_CASE_DEFINITION_BY_SENDER = {
    "creator": [
        ("sender", ["creator"]),
        ("creation", BOOLEAN_VALUES),
        ("error", BOOLEAN_VALUES),
        ("balance_creator", BALANCE_VALUES),
        ("balance_contract", BALANCE_VALUES),
        ("balance_other_positive", BOOLEAN_VALUES),
        ("balance_other_negative", BOOLEAN_VALUES),
    ],
    "other": [
        ("sender", ["other"]),
        ("error", BOOLEAN_VALUES),
        ("balance_creator", BALANCE_VALUES),
        ("balance_contract", BALANCE_VALUES),
        ("balance_sender", BALANCE_VALUES),
        ("balance_other_positive", BOOLEAN_VALUES),
        ("balance_other_negative", BOOLEAN_VALUES),
    ],
}


class InvalidFundFlowCaseException(Exception):

    def __init__(self, transaction_hash, values):
        super(InvalidFundFlowCaseException, self).__init__(
            "The transaction {} was transformed into an invalid case: {}".format(transaction_hash, values))


def build_fund_flow_cases():
    fund_flow_case_id = 1
    fund_flow_case_id_by_name = {}
    for fund_flow_case in convert_fund_flow_case_definition_to_instances():
        assert fund_flow_case not in fund_flow_case_id_by_name
        fund_flow_case_id_by_name[fund_flow_case] = fund_flow_case_id
        fund_flow_case_id += 1
    return fund_flow_case_id_by_name


def convert_fund_flow_case_definition_to_instances(to_define=None, defined=None):
    # if all values are yet to be defined
    if defined is None:
        defined = {}

    # there is no sender defined
    if "sender" not in defined:
        for sender in FUND_FLOW_CASE_DEFINITION_BY_SENDER.keys():
            defined["sender"] = sender
            for fund_flow_case in convert_fund_flow_case_definition_to_instances(defined=defined):
                yield fund_flow_case
        defined.pop("sender")

    # the sender is already defined
    else:
        # get the definition
        definition = FUND_FLOW_CASE_DEFINITION_BY_SENDER[defined["sender"]]

        # allow some values to be initially defined at the start of the recursion
        if to_define is None:
            to_define = [(key, possible_values) for key, possible_values in definition if key not in defined]

        # base case: all keys have values defined, yield the fund flow case
        if len(to_define) == 0:
            if fund_flow_case_is_valid(defined):
                yield create_fund_flow_case(defined)

        # recursion: take the next key and make a new fund flow case for each possible value
        else:
            key, possible_values = to_define[0]
            for possible_value in possible_values:
                defined[key] = possible_value
                for fund_flow_case in convert_fund_flow_case_definition_to_instances(
                        to_define=to_define[1:], defined=defined):
                    yield fund_flow_case
            defined.pop(key)


def create_fund_flow_case(values):
    definition = FUND_FLOW_CASE_DEFINITION_BY_SENDER[values["sender"]]
    return ", ".join([
        "{}={}".format(key, str(values[key]))
        for key, _ in definition  # to assure always the same order from the definition
    ])


def create_fund_flow_case_if_valid(transaction, values):
    if fund_flow_case_is_valid(values):
        return create_fund_flow_case(values)
    else:
        # this should never happen
        raise InvalidFundFlowCaseException(transaction["hash"], str(values))


def fund_flow_case_is_valid(values):
    # check the definition
    if ("sender" not in values) or values["sender"] not in FUND_FLOW_CASE_DEFINITION_BY_SENDER:
        return False
    definition = FUND_FLOW_CASE_DEFINITION_BY_SENDER[values["sender"]]

    # check all values defined and valid
    valid_keys = []
    for key, valid_values in definition:
        valid_keys.append(key)
        if (key not in values) or (values[key] not in valid_values):
            return False

    # initialize with checking the balance of the other accounts
    has_positive = values.get("balance_other_positive", False)
    has_negative = values.get("balance_other_negative", False)

    # go through all the values
    for key, value in values.items():
        # check the key is not extra (not caught in the check above)
        if key not in valid_keys:
            return False

        # check the balances
        has_positive = has_positive or (value == "positive")
        has_negative = has_negative or (value == "negative")

    # there is at least one positive if and only if there is at least one negative
    return has_positive == has_negative


FUND_FLOW_CASE_ID_BY_NAME = build_fund_flow_cases()
