#!/usr/bin/env bash
set -euo pipefail

data_dir=/var/lib/openldap/data
runtime_dir=/run/openldap
config_file=/etc/openldap/slapd.conf

mkdir -p "${data_dir}" "${runtime_dir}" /etc/openldap
chown -R openldap:openldap /var/lib/openldap "${runtime_dir}"

if [[ ! -f "${data_dir}/data.mdb" ]]; then
  admin_hash="$(slappasswd -s "${LDAP_ADMIN_PASSWORD}")"
  analyst_hash="$(slappasswd -s "${LDAP_ANALYST_PASSWORD}")"
  engineer_hash="$(slappasswd -s "${LDAP_ENGINEER_PASSWORD}")"
  cube_hash="$(slappasswd -s "${CUBE_LDAP_PASSWORD}")"

  sed \
    -e "s|__LDAP_ADMIN_HASH__|${admin_hash}|" \
    /opt/openldap/etc/openldap/slapd.conf.template > "${config_file}"
  sed \
    -e "s|__ANALYST_USERNAME__|${LDAP_ANALYST_USERNAME}|g" \
    -e "s|__ENGINEER_USERNAME__|${LDAP_ENGINEER_USERNAME}|g" \
    -e "s|__ANALYST_HASH__|${analyst_hash}|" \
    -e "s|__ENGINEER_HASH__|${engineer_hash}|" \
    -e "s|__CUBE_HASH__|${cube_hash}|" \
    /opt/openldap/etc/openldap/seed.ldif.template > /tmp/seed.ldif
  slapadd -f "${config_file}" -l /tmp/seed.ldif
  chown -R openldap:openldap "${data_dir}"
  rm -f /tmp/seed.ldif
elif [[ ! -f "${config_file}" ]]; then
  admin_hash="$(slappasswd -s "${LDAP_ADMIN_PASSWORD}")"
  sed -e "s|__LDAP_ADMIN_HASH__|${admin_hash}|" \
    /opt/openldap/etc/openldap/slapd.conf.template > "${config_file}"
fi

/opt/openldap/libexec/slapd \
  -u openldap -g openldap \
  -f "${config_file}" \
  -h "ldap://0.0.0.0:389 ldaps://0.0.0.0:636" \
  -d 0 &
slapd_pid=$!

for _ in {1..30}; do
  if ldapwhoami -x -H ldap://127.0.0.1:389 \
    -D "cn=admin,dc=lakehouse,dc=local" \
    -w "${LDAP_ADMIN_PASSWORD}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

ldap_args=(
  -x -H ldap://127.0.0.1:389
  -D "cn=admin,dc=lakehouse,dc=local"
  -w "${LDAP_ADMIN_PASSWORD}"
)

# Stable employee markers allow configured usernames to change without duplicates.
find_managed_dn() {
  local marker="$1"
  local legacy_uid="$2"
  local found
  found="$(ldapsearch "${ldap_args[@]}" -LLL \
    -b "ou=people,dc=lakehouse,dc=local" \
    "(employeeNumber=${marker})" dn |
    sed -n 's/^dn: //p' | head -n 1)"
  if [[ -z "${found}" ]]; then
    found="$(ldapsearch "${ldap_args[@]}" -LLL \
      -b "uid=${legacy_uid},ou=people,dc=lakehouse,dc=local" \
      -s base '(objectClass=*)' dn 2>/dev/null |
      sed -n 's/^dn: //p' | head -n 1)"
  fi
  printf '%s' "${found}"
}

reconcile_user() {
  local username="$1"
  local password="$2"
  local marker="$3"
  local legacy_uid="$4"
  local common_name="$5"
  local surname="$6"
  local given_name="$7"
  local email="$8"
  local desired_dn="uid=${username},ou=people,dc=lakehouse,dc=local"
  local previous_dn
  local password_hash
  previous_dn="$(find_managed_dn "${marker}" "${legacy_uid}")"
  password_hash="$(slappasswd -s "${password}")"

  if ldapsearch "${ldap_args[@]}" -LLL -b "${desired_dn}" \
    -s base '(objectClass=*)' dn >/dev/null 2>&1; then
    ldapmodify "${ldap_args[@]}" >/dev/null <<EOF
dn: ${desired_dn}
changetype: modify
replace: uid
uid: ${username}
-
replace: cn
cn: ${common_name}
-
replace: sn
sn: ${surname}
-
replace: givenName
givenName: ${given_name}
-
replace: mail
mail: ${email}
-
replace: employeeNumber
employeeNumber: ${marker}
-
replace: userPassword
userPassword: ${password_hash}
EOF
  else
    ldapadd "${ldap_args[@]}" >/dev/null <<EOF
dn: ${desired_dn}
objectClass: inetOrgPerson
uid: ${username}
cn: ${common_name}
sn: ${surname}
givenName: ${given_name}
mail: ${email}
employeeNumber: ${marker}
userPassword: ${password_hash}
EOF
  fi

  printf '%s' "${previous_dn}"
}

previous_analyst_dn="$(reconcile_user \
  "${LDAP_ANALYST_USERNAME}" "${LDAP_ANALYST_PASSWORD}" \
  lakehouse-demo-analyst alice.analyst \
  "Alice Analyst" Analyst Alice alice.analyst@lakehouse.local)"
previous_engineer_dn="$(reconcile_user \
  "${LDAP_ENGINEER_USERNAME}" "${LDAP_ENGINEER_PASSWORD}" \
  lakehouse-demo-engineer bob.engineer \
  "Bob Engineer" Engineer Bob bob.engineer@lakehouse.local)"

ldapmodify "${ldap_args[@]}" >/dev/null <<EOF
dn: cn=lakehouse_analysts,ou=groups,dc=lakehouse,dc=local
changetype: modify
replace: member
member: uid=${LDAP_ANALYST_USERNAME},ou=people,dc=lakehouse,dc=local

dn: cn=lakehouse_engineers,ou=groups,dc=lakehouse,dc=local
changetype: modify
replace: member
member: uid=${LDAP_ENGINEER_USERNAME},ou=people,dc=lakehouse,dc=local

dn: cn=lakehouse_services,ou=groups,dc=lakehouse,dc=local
changetype: modify
replace: member
member: uid=svc_cube,ou=people,dc=lakehouse,dc=local
EOF

desired_analyst_dn="uid=${LDAP_ANALYST_USERNAME},ou=people,dc=lakehouse,dc=local"
desired_engineer_dn="uid=${LDAP_ENGINEER_USERNAME},ou=people,dc=lakehouse,dc=local"
if [[ -n "${previous_analyst_dn}" && "${previous_analyst_dn}" != "${desired_analyst_dn}" ]]; then
  ldapdelete "${ldap_args[@]}" "${previous_analyst_dn}"
fi
if [[ -n "${previous_engineer_dn}" && "${previous_engineer_dn}" != "${desired_engineer_dn}" ]]; then
  ldapdelete "${ldap_args[@]}" "${previous_engineer_dn}"
fi

trap 'kill -TERM "${slapd_pid}" 2>/dev/null || true' TERM INT
wait "${slapd_pid}"
