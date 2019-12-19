import logging
import sqlalchemy

from honeypot_detection import etherscan


logging.basicConfig(level="INFO")


def create_etherscan_client():
    return etherscan.Client("ABC123")


def create_sqlalchemy_engine():
    return sqlalchemy.create_engine("sqlite:///honeypot-detection.db")
