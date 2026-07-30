import os

from flask_appbuilder.security.manager import AUTH_LDAP

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
AUTH_USER_REGISTRATION_ROLE = "Viewer"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "cn=lakehouse_analysts,ou=groups,dc=lakehouse,dc=local": ["Viewer"],
    "cn=lakehouse_engineers,ou=groups,dc=lakehouse,dc=local": ["Op"],
}

