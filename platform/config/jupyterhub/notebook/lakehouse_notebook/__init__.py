from .auth import get_token
from .spark import LakehouseSparkBuilder
from .sql_magic import SqlMagics


def load_ipython_extension(ipython):
    ipython.register_magics(SqlMagics)
    ipython.push({"spark_builder": LakehouseSparkBuilder(), "get_token": get_token})
