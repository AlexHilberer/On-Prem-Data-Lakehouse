import os
import pwd
import subprocess
import sys

from oauthenticator.generic import GenericOAuthenticator

ISSUER = "https://authentik.lakehouse.local/application/o/lakehouse/"
ALLOWED_GROUPS = {"lakehouse_analysts", "lakehouse_engineers"}

c = get_config()  # noqa: F821

c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.hub_ip = "127.0.0.1"
c.JupyterHub.cookie_secret_file = "/data/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////data/jupyterhub.sqlite"
c.JupyterHub.default_url = "/hub/home"

c.JupyterHub.authenticator_class = GenericOAuthenticator
c.GenericOAuthenticator.client_id = "lakehouse"
c.GenericOAuthenticator.client_secret = os.environ["OIDC_CLIENT_SECRET"]
c.GenericOAuthenticator.oauth_callback_url = "https://jupyter.lakehouse.local/hub/oauth_callback"
c.GenericOAuthenticator.authorize_url = ISSUER.replace("/o/lakehouse/", "/o/authorize/")
c.GenericOAuthenticator.token_url = ISSUER.replace("/o/lakehouse/", "/o/token/")
c.GenericOAuthenticator.userdata_url = ISSUER.replace("/o/lakehouse/", "/o/userinfo/")
c.GenericOAuthenticator.scope = ["openid", "profile", "email", "offline_access"]
c.GenericOAuthenticator.username_claim = "preferred_username"
# tornado's curl client ignores SSL_CERT_FILE, so the local CA is passed explicitly.
c.GenericOAuthenticator.http_request_kwargs = {"ca_certs": "/run/certs/ca.crt"}
c.GenericOAuthenticator.manage_groups = True
c.GenericOAuthenticator.claim_groups_key = "groups"
c.GenericOAuthenticator.allowed_groups = ALLOWED_GROUPS
c.GenericOAuthenticator.enable_auth_state = True

c.JupyterHub.spawner_class = "jupyterhub.spawner.LocalProcessSpawner"
c.Spawner.default_url = "/lab"
c.Spawner.cmd = ["jupyterhub-singleuser"]


async def prepare_kernel_environment(spawner):
    # LocalProcessSpawner needs a Linux user; useradd accepts dotted names.
    try:
        pwd.getpwnam(spawner.user.name)
    except KeyError:
        subprocess.run(["useradd", "-m", "-s", "/bin/bash", spawner.user.name], check=True)
    # Linux users are recreated with new IDs when the container is, but /home persists.
    account = pwd.getpwnam(spawner.user.name)
    if os.stat(account.pw_dir).st_uid != account.pw_uid:
        subprocess.run(
            ["chown", "-R", f"{account.pw_uid}:{account.pw_gid}", account.pw_dir], check=True
        )
    spawner.environment.update(
        {
            "PYTHONPATH": "/opt/lakehouse-notebook",
            "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64",
            "SSL_CERT_FILE": "/run/certs/ca.crt",
            "REQUESTS_CA_BUNDLE": "/run/certs/ca.crt",
            "TRINO_URL": "https://trino:8443",
            "POLARIS_URI": "http://polaris:8181/api/catalog",
            "POLARIS_WAREHOUSE": "lakehouse",
            "LAKEHOUSE_TOKEN_URL": "http://127.0.0.1:8000/services/token-broker/token",
            "GARAGE_ACCESS_KEY": os.environ["GARAGE_ACCESS_KEY"],
            "GARAGE_SECRET_KEY": os.environ["GARAGE_SECRET_KEY"],
        }
    )


c.Spawner.pre_spawn_hook = prepare_kernel_environment
# authentik refresh tokens are single use, so only the token broker may refresh them.
c.Authenticator.auth_refresh_age = 0
c.Authenticator.refresh_pre_spawn = False

c.JupyterHub.services = [
    {
        "name": "token-broker",
        "url": "http://127.0.0.1:8090",
        "command": [sys.executable, "/srv/jupyterhub/token_broker.py"],
        "environment": {
            "OIDC_CLIENT_SECRET": os.environ["OIDC_CLIENT_SECRET"],
            "SSL_CERT_FILE": "/run/certs/ca.crt",
            "REQUESTS_CA_BUNDLE": "/run/certs/ca.crt",
        },
    }
]
c.JupyterHub.load_roles = [
    {"name": "user", "scopes": ["self", "access:services!service=token-broker"]},
    # Kernels call the broker with the server token, whose scopes the user role caps.
    {
        "name": "server",
        "scopes": [
            "users:activity!user",
            "access:servers!server",
            "access:services!service=token-broker",
        ],
    },
    {
        "name": "token-broker",
        "scopes": ["read:users", "admin:users", "admin:auth_state"],
        "services": ["token-broker"],
    },
]
