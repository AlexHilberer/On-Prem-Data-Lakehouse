FROM apache/polaris-admin-tool:1.6.0 AS admin

FROM apache/polaris:1.6.0

USER root
COPY --from=admin /deployments/ /opt/polaris-admin/
COPY platform/images/polaris/entrypoint.sh /usr/local/bin/polaris-entrypoint
RUN chmod 0755 /usr/local/bin/polaris-entrypoint \
    && chown -R polaris:polaris /opt/polaris-admin
USER polaris

ENTRYPOINT ["/usr/local/bin/polaris-entrypoint"]
