import os

from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    "postgresql+psycopg2://superset:"
    f"{os.environ['SUPERSET_DB_PASSWORD']}@postgres:5432/superset"
)
WTF_CSRF_ENABLED = True
ENABLE_PROXY_FIX = True

ISSUER = "https://authentik.lakehouse.local/application/o/lakehouse/"
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [
    {
        "name": "authentik",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "lakehouse",
            "client_secret": os.environ["OIDC_CLIENT_SECRET"],
            "server_metadata_url": f"{ISSUER}.well-known/openid-configuration",
            "api_base_url": ISSUER,
            "client_kwargs": {"scope": "openid profile email"},
        },
    }
]


class LakehouseSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        claims = self.oauth_remotes[provider].get(
            "https://authentik.lakehouse.local/application/o/userinfo/"
        ).json()
        return {
            "username": claims["preferred_username"],
            "first_name": claims.get("given_name", ""),
            "last_name": claims.get("family_name", ""),
            "email": claims.get("email", ""),
            "role_keys": claims.get("groups", []),
        }


CUSTOM_SECURITY_MANAGER = LakehouseSecurityManager
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "lakehouse_analysts": ["Gamma"],
    "lakehouse_engineers": ["Alpha"],
}
FEATURE_FLAGS = {"DASHBOARD_RBAC": True}
RECAPTCHA_PUBLIC_KEY = ""
ROW_LIMIT = 10000
SUPERSET_WEBSERVER_TIMEOUT = 120
