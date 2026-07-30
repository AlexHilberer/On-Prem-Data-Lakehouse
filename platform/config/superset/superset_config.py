import os

from flask_appbuilder.security.manager import AUTH_LDAP

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    "postgresql+psycopg2://superset:"
    f"{os.environ['SUPERSET_DB_PASSWORD']}@postgres:5432/superset"
)
WTF_CSRF_ENABLED = True
ENABLE_PROXY_FIX = True
AUTH_TYPE = AUTH_LDAP
AUTH_LDAP_SERVER = "ldaps://openldap:636"
AUTH_LDAP_USE_TLS = False
AUTH_LDAP_ALLOW_SELF_SIGNED = True
AUTH_LDAP_SEARCH = "ou=people,dc=lakehouse,dc=local"
AUTH_LDAP_BIND_USER = "cn=admin,dc=lakehouse,dc=local"
AUTH_LDAP_BIND_PASSWORD = os.environ["LDAP_ADMIN_PASSWORD"]
AUTH_LDAP_UID_FIELD = "uid"
AUTH_LDAP_FIRSTNAME_FIELD = "givenName"
AUTH_LDAP_LASTNAME_FIELD = "sn"
AUTH_LDAP_EMAIL_FIELD = "mail"
AUTH_LDAP_GROUP_FIELD = "memberOf"
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "cn=lakehouse_analysts,ou=groups,dc=lakehouse,dc=local": ["Gamma"],
    "cn=lakehouse_engineers,ou=groups,dc=lakehouse,dc=local": ["Alpha"],
}
FEATURE_FLAGS = {"DASHBOARD_RBAC": True}
RECAPTCHA_PUBLIC_KEY = ""
ROW_LIMIT = 10000
SUPERSET_WEBSERVER_TIMEOUT = 120
