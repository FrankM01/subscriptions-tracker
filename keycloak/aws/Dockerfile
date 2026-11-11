FROM quay.io/keycloak/keycloak:26.7.3

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true

RUN /opt/keycloak/bin/kc.sh build

COPY --chown=keycloak:keycloak keycloak/aws/realms/ /opt/keycloak/data/import/

CMD ["start", "--optimized", "--import-realm"]
