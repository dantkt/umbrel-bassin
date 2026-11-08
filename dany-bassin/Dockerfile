FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git yasm autoconf automake libtool pkg-config ca-certificates libzmq3-dev && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://bitbucket.org/ckolivas/ckpool-solo.git /src && cd /src && ./autogen.sh && ./configure && make -j2

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 libzmq5 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/src/ckpool /usr/local/bin/ckpool
COPY server.py index.html entrypoint.sh /app/
WORKDIR /app
RUN chmod +x /app/entrypoint.sh
EXPOSE 8080 3333
CMD ["/app/entrypoint.sh"]
