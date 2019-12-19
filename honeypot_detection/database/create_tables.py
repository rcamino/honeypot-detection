from honeypot_detection import config

from honeypot_detection.database.all_tables import Base


def main():
    sqlalchemy_engine = config.create_sqlalchemy_engine()
    Base.metadata.create_all(sqlalchemy_engine)


if __name__ == '__main__':
    main()
