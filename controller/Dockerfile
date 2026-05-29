FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && pip install --no-cache-dir "setuptools<58" "dnspython<2" "eventlet==0.30.2" \
    && pip install --no-cache-dir ryu==4.34 \
    && apt-get purge -y --auto-remove gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY controller/ /app/

EXPOSE 6633 8080

CMD ["ryu-manager", "/app/ryu_controller.py", "--ofp-tcp-listen-port", "6633"]
