import logging
import requests
import time


logger = logging.getLogger(__name__)


class EtherscanIoException(Exception):
    pass


class EtherscanInvalidArgument(Exception):
    pass


class Client:
    """
    A simple client for the Etherscan RESTS API.
    Only allows to fetch the list of transactions for a given address.

    Based on: https://github.com/neoctobers/etherscan
    For more information: https://etherscan.io/apis
    """
    
    API_URL = "https://api.etherscan.io/api"
    MAX_REQUESTS_PER_SECOND = 5
    REQUEST_LIMIT = 10000

    TRANSACTION_TYPE_NORMAL = "normal"
    TRANSACTION_TYPE_INTERNAL = "internal"

    BYTE_CODE_TAG_LATEST = "latest"
    BYTE_CODE_TAG_EARLIEST = "earliest"
    BYTE_CODE_TAG_PENDING = "pending"

    def __init__(self, api_key):
        self.api_key = api_key

        self.session = None
        self.time_window_start = None
        self.time_window_count = 0

    def get_contract_byte_code_by_address(self, address, tag=BYTE_CODE_TAG_LATEST):
        parameters = {
            "module": "proxy",
            "action": "eth_getCode",
            "tag": tag,
            "address": address
        }

        return self._request(parameters)

    def get_contract_source_code_by_address(self, address):
        parameters = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address
        }

        results = self._request(parameters)

        assert len(results) == 1

        return results[0]

    def list_transactions_by_address(self,
                                     address,
                                     transaction_type=TRANSACTION_TYPE_NORMAL,
                                     start_block=0,
                                     end_block=99999999,
                                     page=1,
                                     offset=REQUEST_LIMIT,
                                     sort="asc"):
        parameters = {
            "module": "account",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
        }
        
        if transaction_type == self.TRANSACTION_TYPE_NORMAL:
            parameters["action"] = "txlist"
        elif transaction_type == self.TRANSACTION_TYPE_INTERNAL:
            parameters["action"] = "txlistinternal"
        else:
            raise EtherscanInvalidArgument("Transaction type must be '{}' or '{}'.".format(
                self.TRANSACTION_TYPE_NORMAL, self.TRANSACTION_TYPE_INTERNAL))

        return self._request(parameters)

    def _reset_time_window(self):
        self.time_window_start = time.time()
        self.time_window_count = 0

    def _request(self, parameters):
        parameters["apikey"] = self.api_key

        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({"User-agent": "python wrapper"})

        # if it's the first request or the time window ended
        if self.time_window_start is None or time.time() - self.time_window_start > 1:
            self._reset_time_window()
        # if inside the time window and the request count reached the limit
        elif self.time_window_count >= self.MAX_REQUESTS_PER_SECOND:
            logger.info("Waiting before sending more requests...")
            time.sleep(1)
            logger.info("Continue to request.")
            self._reset_time_window()

        response = self.session.post(url=self.API_URL, data=parameters).json()

        self.time_window_count += 1

        # JSON RPC error handling
        if "jsonrpc" in response:
            if "error" in response:
                raise EtherscanIoException(response["message"])

        # non JSON RPC error handling
        else:
            if "0" == response["status"] and response["message"] != "No transactions found":
                raise EtherscanIoException(response["message"])

        return response["result"]

    @staticmethod
    def parse_bool(value):
        if value.lower() in ["0", "false", "none", "null", "n/a", ""]:
            return False
        return True

    @staticmethod
    def parse_int(value):
        if value == "":
            return None
        return int(value)

    @staticmethod
    def parse_str(value):
        if value == "":
            return None
        return value

    @staticmethod
    def parse_value(value):
        if value == "":
            return None
        return int(value) / 1e18
