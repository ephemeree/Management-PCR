FROM mysql:8.0

# Schema is baked into the image applied automatically on first start.
COPY schema.sql /docker-entrypoint-initdb.d/01-schema.sql
