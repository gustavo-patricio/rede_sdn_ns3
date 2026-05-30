# Documentacao da API REST

Base URL local:

```text
http://localhost:8000
```

Documentacao interativa:

```text
http://localhost:8000/docs
```

Todos os endpoints retornam JSON. Os endpoints `POST` atuais nao exigem corpo na requisicao; eles executam uma acao operacional no ambiente Docker.

## Valores Padrao

Grupos validos:

```text
uti
enfermaria
triagem
```

Containers principais:

```text
controller
dashboard
server
gw-uti
gw-enfermaria
gw-triagem
sensor-uti-1
sensor-uti-2
sensor-uti-3
sensor-enfermaria-1
sensor-enfermaria-2
sensor-enfermaria-3
sensor-triagem-1
sensor-triagem-2
sensor-triagem-3
```

## Modelos de Resposta

### CommandResult

Usado por endpoints que executam comandos dentro de containers.

```json
{
  "container": "gw-enfermaria",
  "command": ["tc", "qdisc", "show", "dev", "eth1"],
  "exit_code": 0,
  "output": "qdisc noqueue 0: root refcnt 2 \n"
}
```

### GroupMetrics

Usado por metricas de trafego de um grupo.

```json
{
  "group": "enfermaria",
  "messages": 36,
  "bytes": 5793,
  "duration_seconds": 22.0,
  "messages_per_second": 1.636,
  "throughput_bps": 2106.545,
  "avg_delay_ms": 0.42,
  "jitter_ms": 0.148,
  "expected_messages": 36,
  "missing_messages": 0,
  "packet_loss_percent": 0.0
}
```

### TrafficMetrics

Usado por metricas agregadas de todos os grupos.

```json
{
  "source": "server logs tail=1000",
  "parsed_lines": 117,
  "ignored_lines": 1,
  "groups": {
    "uti": {},
    "enfermaria": {},
    "triagem": {}
  }
}
```

## Sistema

### GET /health

Verifica se a API consegue acessar o Docker.

Request:

```http
GET /health
```

Body: nenhum.

Response:

```json
{
  "status": "ok",
  "docker": "ok"
}
```

### GET /status

Retorna o estado esperado dos servicos do projeto.

Request:

```http
GET /status
```

Body: nenhum.

Response:

```json
{
  "project": "atividad_6",
  "total_containers": 15,
  "running": 15,
  "services": {
    "controller": "running",
    "dashboard": "running",
    "server": "running",
    "gw-uti": "running"
  }
}
```

### GET /containers

Lista os containers do projeto Docker Compose.

Request:

```http
GET /containers
```

Body: nenhum.

Response:

```json
[
  {
    "name": "server",
    "service": "server",
    "status": "running",
    "image": "atividad_6-server:latest",
    "id": "a0bc3ddf3fda"
  }
]
```

## Logs

### GET /logs/{container_name}

Retorna logs de um container.

Path params:

| Parametro | Tipo | Obrigatorio | Exemplo |
|---|---|---:|---|
| `container_name` | string | sim | `server` |

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `80` | `1` a `500` |

Request:

```http
GET /logs/server?tail=100
```

Body: nenhum.

Response:

```json
{
  "container": "server",
  "logs": "[HOSPITAL] servidor UDP ativo em 0.0.0.0:9000\n..."
}
```

## Grupos

### GET /groups

Lista os grupos, sensores e gateways.

Request:

```http
GET /groups
```

Body: nenhum.

Response:

```json
[
  {
    "group": "uti",
    "gateway": "gw-uti",
    "sensors": ["sensor-uti-1", "sensor-uti-2", "sensor-uti-3"]
  }
]
```

### GET /groups/{group}

Retorna dados basicos de um grupo.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `group` | string | sim | `uti`, `enfermaria`, `triagem` |

Request:

```http
GET /groups/enfermaria
```

Body: nenhum.

### GET /groups/{group}/sensors

Retorna sensores de um grupo.

Request:

```http
GET /groups/uti/sensors
```

Body: nenhum.

Response:

```json
{
  "group": "uti",
  "sensors": ["sensor-uti-1", "sensor-uti-2", "sensor-uti-3"]
}
```

### GET /groups/{group}/gateway

Retorna o gateway associado ao grupo.

Request:

```http
GET /groups/triagem/gateway
```

Body: nenhum.

Response:

```json
{
  "group": "triagem",
  "gateway": "gw-triagem"
}
```

### GET /groups/{group}/gateway/interfaces

Retorna interfaces do gateway do grupo.

Request:

```http
GET /groups/enfermaria/gateway/interfaces
```

Body: nenhum.

Response: `CommandResult`.

### GET /groups/{group}/gateway/iptables

Retorna regras `iptables` do gateway do grupo.

Request:

```http
GET /groups/triagem/gateway/iptables
```

Body: nenhum.

Response: `CommandResult`.

### GET /groups/{group}/gateway/tc

Retorna regras `tc qdisc` do gateway do grupo.

Request:

```http
GET /groups/enfermaria/gateway/tc
```

Body: nenhum.

Response: `CommandResult`.

### GET /groups/{group}/routes

Retorna rotas do gateway e dos sensores do grupo.

Request:

```http
GET /groups/enfermaria/routes
```

Body: nenhum.

Response:

```json
{
  "group": "enfermaria",
  "gateway": {
    "container": "gw-enfermaria",
    "command": ["ip", "route"],
    "exit_code": 0,
    "output": "..."
  },
  "sensors": {
    "sensor-enfermaria-1": {
      "container": "sensor-enfermaria-1",
      "command": ["ip", "route"],
      "exit_code": 0,
      "output": "..."
    }
  }
}
```

### GET /groups/{group}/logs

Retorna somente linhas do log do servidor relacionadas ao grupo.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `group` | string | sim | `uti`, `enfermaria`, `triagem` |

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `200` | `1` a `1000` |

Request:

```http
GET /groups/uti/logs?tail=100
```

Body: nenhum.

Response:

```json
{
  "group": "uti",
  "source": "server",
  "logs": [
    "[2026-05-30 14:34:15] [HOSPITAL] grupo=UTI ..."
  ]
}
```

### GET /groups/{group}/metrics

Retorna metricas de trafego de um grupo.

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `1000` | `10` a `5000` |

Request:

```http
GET /groups/enfermaria/metrics?tail=1000
```

Body: nenhum.

Response: `GroupMetrics`.

## Metricas Agregadas

### GET /metrics/traffic

Retorna metricas de todos os grupos calculadas a partir dos logs do servidor.

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `1000` | `10` a `5000` |

Request:

```http
GET /metrics/traffic?tail=1000
```

Body: nenhum.

Response: `TrafficMetrics`.

### GET /metrics/traffic/{group}

Alias antigo para `GET /groups/{group}/metrics`.

Request:

```http
GET /metrics/traffic/uti
```

Body: nenhum.

Response: `GroupMetrics`.

## Politicas

### POST /policies/enfermaria/limit

Aplica limitacao de banda no gateway da enfermaria.

Request:

```http
POST /policies/enfermaria/limit
Content-Type: application/json
```

Body: nenhum. Enviar `{}` tambem e aceito pelo cliente HTTP, mas a API ignora o corpo.

Response: `CommandResult`.

### POST /policies/enfermaria/restore

Remove a limitacao aplicada no gateway da enfermaria.

Request:

```http
POST /policies/enfermaria/restore
Content-Type: application/json
```

Body: nenhum.

Response: `CommandResult`.

### POST /policies/triagem/block

Bloqueia o trafego da triagem para o servidor hospitalar.

Request:

```http
POST /policies/triagem/block
Content-Type: application/json
```

Body: nenhum.

Response: `CommandResult`.

### POST /policies/triagem/unblock

Remove o bloqueio do trafego da triagem.

Request:

```http
POST /policies/triagem/unblock
Content-Type: application/json
```

Body: nenhum.

Response: `CommandResult`.

### POST /policies/restore

Restaura todas as politicas dinamicas aplicadas pela API.

Request:

```http
POST /policies/restore
Content-Type: application/json
```

Body: nenhum.

Response:

```json
{
  "enfermaria": {
    "container": "gw-enfermaria",
    "command": ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/restaurar_politicas.sh"],
    "exit_code": 0,
    "output": "Politicas restauradas...\n"
  },
  "triagem": {
    "container": "gw-triagem",
    "command": ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"],
    "exit_code": 0,
    "output": "Politicas restauradas...\n"
  }
}
```

## Exemplos para Frontend

### Buscar status geral

```javascript
const response = await fetch("http://localhost:8000/status");
const status = await response.json();
```

### Buscar metricas da enfermaria

```javascript
const response = await fetch("http://localhost:8000/groups/enfermaria/metrics?tail=1000");
const metrics = await response.json();
```

### Aplicar limitacao de banda

```javascript
const response = await fetch("http://localhost:8000/policies/enfermaria/limit", {
  method: "POST",
});
const result = await response.json();
```

### Restaurar politicas

```javascript
const response = await fetch("http://localhost:8000/policies/restore", {
  method: "POST",
});
const result = await response.json();
```

## Observacoes de Integracao

- A API nao exige autenticacao no ambiente atual.
- Os `POST` de politica nao recebem payload.
- Use `exit_code === 0` em `CommandResult` para confirmar sucesso operacional.
- Para atualizar dashboards em tempo real, consulte `GET /groups/{group}/metrics` periodicamente.
- Para logs, prefira `GET /groups/{group}/logs` em telas por setor e `GET /logs/server` em telas gerais.
