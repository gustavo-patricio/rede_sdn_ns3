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

### SensorMetrics

Usado por metricas calculadas por sensor a partir dos logs do servidor.

```json
{
  "group": "uti",
  "sensor": "sensor-cardiaco",
  "origins": ["10.0.1.11:45612"],
  "messages": 30,
  "bytes": 4380,
  "duration_seconds": 58.0,
  "messages_per_second": 0.517,
  "throughput_bps": 604.138,
  "avg_payload_bytes": 146.0,
  "avg_delay_ms": 0.431,
  "min_delay_ms": 0.289,
  "max_delay_ms": 0.813,
  "jitter_ms": 0.102,
  "expected_messages": 30,
  "missing_messages": 0,
  "packet_loss_percent": 0.0,
  "first_seen": "2026-05-30T14:05:10",
  "last_seen": "2026-05-30T14:06:08",
  "last_sequence": 90,
  "last_reading": {
    "batimento_bpm": 88
  },
  "reading_stats": {
    "batimento_bpm": {
      "samples": 30,
      "min": 72,
      "max": 97,
      "avg": 84.633,
      "last": 88
    }
  }
}
```

### SensorMetricsCollection

Usado por `GET /sensors/metrics`.

```json
{
  "source": "server logs tail=1000",
  "parsed_lines": 117,
  "ignored_lines": 1,
  "groups": {
    "uti": {
      "sensor-cardiaco": {}
    },
    "enfermaria": {},
    "triagem": {}
  }
}
```

### GatewayStatus

Usado por `GET /gateways`.

```json
{
  "group": "enfermaria",
  "container": "gw-enfermaria",
  "docker_status": "running",
  "running": true,
  "image": "atividad_6-gw-enfermaria:latest",
  "id": "18dc4007211e",
  "ip_forward": "1",
  "interfaces": "lo UNKNOWN 127.0.0.1/8 ::1/128\neth0@if66 UP 10.0.2.1/24\neth1@if70 UP 10.0.100.2/24\n",
  "tc_eth1": "qdisc noqueue 0: root refcnt 2 \n",
  "policies": {
    "bandwidth_limit_active": false,
    "triage_block_active": false
  }
}
```

### PolicyEndpoint

Usado por `GET /policies` para o frontend descobrir quais acoes de politica existem e como chama-las.

```json
{
  "key": "enfermaria_limit",
  "method": "POST",
  "path": "/policies/enfermaria/limit",
  "group": "enfermaria",
  "action": "limit",
  "description": "Aplica limitacao de banda no gateway da enfermaria.",
  "request_body_required": false,
  "request_body_schema": null,
  "request_example": null,
  "response_model": "CommandResult",
  "status_endpoint": "/gateways"
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

## Gateways

### GET /gateways

Retorna status detalhado dos gateways por grupo.

Request:

```http
GET /gateways
```

Body: nenhum.

Response:

```json
{
  "uti": {
    "group": "uti",
    "container": "gw-uti",
    "docker_status": "running",
    "running": true,
    "image": "atividad_6-gw-uti:latest",
    "id": "8e18a03efd0c",
    "ip_forward": "1",
    "interfaces": "lo UNKNOWN 127.0.0.1/8 ::1/128\neth0@if66 UP 10.0.1.1/24\neth1@if70 UP 10.0.100.1/24\n",
    "tc_eth1": "qdisc noqueue 0: root refcnt 2 \n",
    "policies": {
      "bandwidth_limit_active": false,
      "triage_block_active": false
    }
  },
  "enfermaria": {
    "group": "enfermaria",
    "container": "gw-enfermaria",
    "docker_status": "running",
    "running": true,
    "image": "atividad_6-gw-enfermaria:latest",
    "id": "18dc4007211e",
    "ip_forward": "1",
    "interfaces": "lo UNKNOWN 127.0.0.1/8 ::1/128\neth0@if66 UP 10.0.2.1/24\neth1@if70 UP 10.0.100.2/24\n",
    "tc_eth1": "qdisc tbf 8001: root refcnt 9 rate 256Kbit burst 4Kb lat 400ms \n",
    "policies": {
      "bandwidth_limit_active": true,
      "triage_block_active": false
    }
  },
  "triagem": {
    "group": "triagem",
    "container": "gw-triagem",
    "docker_status": "running",
    "running": true,
    "image": "atividad_6-gw-triagem:latest",
    "id": "d69dcd44d47f",
    "ip_forward": "1",
    "interfaces": "lo UNKNOWN 127.0.0.1/8 ::1/128\neth0@if66 UP 10.0.3.1/24\neth1@if70 UP 10.0.100.3/24\n",
    "tc_eth1": "qdisc noqueue 0: root refcnt 2 \n",
    "policies": {
      "bandwidth_limit_active": false,
      "triage_block_active": true
    }
  }
}
```

Campos principais:

| Campo | Descricao |
|---|---|
| `docker_status` | Estado bruto do container no Docker, como `running` ou `exited`. |
| `running` | Booleano derivado de `docker_status == "running"`. |
| `ip_forward` | Valor de `/proc/sys/net/ipv4/ip_forward` dentro do gateway. |
| `interfaces` | Saida de `ip -br addr` dentro do gateway. |
| `tc_eth1` | Saida de `tc qdisc show dev eth1`. |
| `policies.bandwidth_limit_active` | `true` quando ha qdisc `tbf` ativo no gateway. |
| `policies.triage_block_active` | `true` quando ha regra `DROP` para `10.0.3.0/24 -> 10.0.100.10`. |

### GET /gateways/{gateway}/iptables

Retorna regras `iptables` de um gateway.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `gateway` | string | sim | `uti`, `enfermaria`, `triagem` |

Response: `CommandResult`.

### GET /gateways/{gateway}/tc

Retorna regras `tc qdisc` de um gateway.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `gateway` | string | sim | `uti`, `enfermaria`, `triagem` |

Response: `CommandResult`.

### GET /gateways/{gateway}/interfaces

Retorna interfaces de um gateway.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `gateway` | string | sim | `uti`, `enfermaria`, `triagem` |

Response: `CommandResult`.

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

### GET /sensors/metrics

Retorna metricas por sensor, agrupadas por grupo, sem alterar os endpoints de metricas ja existentes.

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `1000` | `10` a `5000` |

Request:

```http
GET /sensors/metrics?tail=1000
```

Body: nenhum.

Response: `SensorMetricsCollection`.

### GET /groups/{group}/sensors/metrics

Retorna metricas por sensor de um grupo especifico.

Path params:

| Parametro | Tipo | Obrigatorio | Valores |
|---|---|---:|---|
| `group` | string | sim | `uti`, `enfermaria`, `triagem` |

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `1000` | `10` a `5000` |

Request:

```http
GET /groups/uti/sensors/metrics?tail=1000
```

Body: nenhum.

Response:

```json
{
  "sensor-cardiaco": {},
  "sensor-oxigenacao": {},
  "sensor-pressao": {}
}
```

Cada valor do objeto segue o modelo `SensorMetrics`.

### GET /groups/{group}/sensors/{sensor}/metrics

Retorna metricas de um sensor especifico dentro de um grupo. O parametro `sensor` usa o nome registrado no log do servidor, como `sensor-cardiaco`, `sensor-oxigenacao`, `sensor-temperatura` ou `sensor-triagem`.

Path params:

| Parametro | Tipo | Obrigatorio | Exemplo |
|---|---|---:|---|
| `group` | string | sim | `uti` |
| `sensor` | string | sim | `sensor-cardiaco` |

Query params:

| Parametro | Tipo | Obrigatorio | Padrao | Limite |
|---|---|---:|---:|---|
| `tail` | integer | nao | `1000` | `10` a `5000` |

Request:

```http
GET /groups/uti/sensors/sensor-cardiaco/metrics?tail=1000
```

Body: nenhum.

Response: `SensorMetrics`.

## Politicas

As politicas atuais sao acoes fixas. Os endpoints `POST` nao exigem body; o cliente pode enviar a requisicao sem payload.

Para integrar o frontend, use `GET /policies` para listar quais acoes existem, qual rota chamar e se alguma delas exige corpo de requisicao.

### GET /policies

Lista os endpoints de politica disponiveis e o contrato de envio de cada um.

Request:

```http
GET /policies
```

Body: nenhum.

Response:

```json
{
  "enfermaria_limit": {
    "key": "enfermaria_limit",
    "method": "POST",
    "path": "/policies/enfermaria/limit",
    "group": "enfermaria",
    "action": "limit",
    "description": "Aplica limitacao de banda no gateway da enfermaria.",
    "request_body_required": false,
    "request_body_schema": null,
    "request_example": null,
    "response_model": "CommandResult",
    "status_endpoint": "/gateways"
  },
  "enfermaria_restore": {
    "key": "enfermaria_restore",
    "method": "POST",
    "path": "/policies/enfermaria/restore",
    "group": "enfermaria",
    "action": "restore",
    "description": "Remove a limitacao de banda do gateway da enfermaria.",
    "request_body_required": false,
    "request_body_schema": null,
    "request_example": null,
    "response_model": "CommandResult",
    "status_endpoint": "/gateways"
  },
  "triagem_block": {
    "key": "triagem_block",
    "method": "POST",
    "path": "/policies/triagem/block",
    "group": "triagem",
    "action": "block",
    "description": "Bloqueia o trafego da triagem para o servidor hospitalar.",
    "request_body_required": false,
    "request_body_schema": null,
    "request_example": null,
    "response_model": "CommandResult",
    "status_endpoint": "/gateways"
  },
  "triagem_unblock": {
    "key": "triagem_unblock",
    "method": "POST",
    "path": "/policies/triagem/unblock",
    "group": "triagem",
    "action": "unblock",
    "description": "Remove o bloqueio do trafego da triagem.",
    "request_body_required": false,
    "request_body_schema": null,
    "request_example": null,
    "response_model": "CommandResult",
    "status_endpoint": "/gateways"
  },
  "restore_all": {
    "key": "restore_all",
    "method": "POST",
    "path": "/policies/restore",
    "group": null,
    "action": "restore_all",
    "description": "Restaura todas as politicas dinamicas aplicadas pela API.",
    "request_body_required": false,
    "request_body_schema": null,
    "request_example": null,
    "response_model": "dict[str, CommandResult]",
    "status_endpoint": "/gateways"
  }
}
```

Campos principais:

| Campo | Descricao |
|---|---|
| `method` | Metodo HTTP que o frontend deve usar. |
| `path` | Rota que deve ser chamada para executar a politica. |
| `group` | Grupo afetado pela politica. Quando for `null`, a politica afeta mais de um grupo. |
| `request_body_required` | Indica se a rota exige corpo na requisicao. Atualmente todas retornam `false`. |
| `request_body_schema` | Estrutura esperada no body. Atualmente `null` porque as politicas sao fixas. |
| `request_example` | Exemplo de payload. Atualmente `null` porque nao ha payload. |
| `response_model` | Tipo de resposta esperado. |
| `status_endpoint` | Endpoint recomendado para conferir se a politica ficou ativa. |

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
