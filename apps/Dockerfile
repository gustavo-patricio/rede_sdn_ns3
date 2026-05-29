FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/ /app/

CMD ["python3", "/app/servidor_hospitalar.py", "--host", "0.0.0.0", "--port", "9000"]
