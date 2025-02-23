import os

import sqlalchemy.exc
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

class ORM:

    def __init__(self):
        load_dotenv()
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASS')
        host = os.getenv('DB_HOST')
        port = os.getenv('DB_PORT')
        dbname = os.getenv('DB_NAME')
        connection_string = "mysql+mysqldb://%s:%s@%s:%s/%s" % (user, password, host, port, dbname)
        try:
            self.engine = create_engine(connection_string, echo=False)
        except sqlalchemy.exc.OperationalError:
            connection_string = "mysql+mysqldb://%s:%s@%s:%s/%s" % (user, password, 'localhost', port, dbname)
            self.engine = create_engine(connection_string, echo=False)
        self.sessionmaker = sessionmaker(self.engine)
        self.session = self.sessionmaker()

if __name__ == '__main__':
    orm = ORM()
    s1 = orm.sessionmaker()
    s2 = orm.sessionmaker()

    print('success')