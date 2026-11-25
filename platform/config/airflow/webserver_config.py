import os

from airflow.providers.fab.auth_manager.security_manager.override import (
    FabAirflowSecurityManagerOverride,
)
from flask_appbuilder.security.manager import AUTH_OAUTH

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


class LakehouseSecurityManager(FabAirflowSecurityManagerOverride):
    def get_oauth_user_info(self, provider, resp):
        claims = self.oauth_remotes[provider].userinfo(token=resp)
        return {
            "username": claims["preferred_username"],
            "first_name": claims.get("given_name", ""),
            "last_name": claims.get("family_name", ""),
            "email": claims.get("email", ""),
            "role_keys": claims.get("groups", []),
        }


SECURITY_MANAGER_CLASS = LakehouseSecurityManager
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "lakehouse_analysts": ["Viewer"],
    "lakehouse_engineers": ["Op"],
}
