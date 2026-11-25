import os
from urllib.parse import urlparse

import pandas as pd
import trino
from IPython.core.magic import Magics, line_cell_magic, magics_class

from .auth import get_token


@magics_class
class SqlMagics(Magics):
    @line_cell_magic
    def sql(self, line, cell=None):
        """Run a Trino query as the logged-in user and return a DataFrame."""
        query = (cell if cell is not None else line).strip().rstrip(";")
        url = urlparse(os.environ["TRINO_URL"])
        connection = trino.dbapi.connect(
            host=url.hostname,
            port=url.port or 8443,
            http_scheme=url.scheme,
            user=os.environ["JUPYTERHUB_USER"],
            auth=trino.auth.JWTAuthentication(get_token()),
            verify=os.environ["SSL_CERT_FILE"],
            catalog="lakehouse",
            schema="gold",
        )
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        if cursor.description is None:
            return None
        return pd.DataFrame(rows, columns=[column[0] for column in cursor.description])
