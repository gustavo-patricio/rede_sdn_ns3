FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash iproute2 iptables iputils-ping procps tcpdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/vnf
COPY vnf/ /opt/vnf/
RUN chmod +x /opt/vnf/*.sh

CMD ["bash", "-lc", "sleep infinity"]
