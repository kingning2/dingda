FROM rust:1.85-bookworm AS builder

WORKDIR /app

COPY Cargo.toml Cargo.lock* ./
COPY migrations ./migrations
COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/server /usr/local/bin/server
COPY migrations ./migrations

ENV API_HOST=0.0.0.0 \
    API_PORT=8080 \
    MALLOC_ARENA_MAX=2

EXPOSE 8080

CMD ["server"]
