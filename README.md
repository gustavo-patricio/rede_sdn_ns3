# Rede Hospitalar IoMT com SDN, NFV e API REST

Projeto academico da Atividade 6 para simular uma rede hospitalar IoMT com setores isolados, gateways VNF, controlador SDN e uma API REST local para diagnostico, metricas e aplicacao de politicas de rede.

## Visao Geral

A rede representa tres grupos hospitalares:

- `uti`
- `enfermaria`
- `triagem`

Cada grupo possui sensores simulados que enviam leituras UDP para um servidor hospitalar central. O trafego de cada grupo passa por um gateway VNF especifico:

| Grupo | Rede | Gateway | Sensores |
|---|---|---|---|
| `uti` | `10.0.1.0/24` | `gw-uti` | `sensor-uti-1`, `sensor-uti-2`, `sensor-uti-3` |
| `enfermaria` | `10.0.2.0/24` | `gw-enfermaria` | `sensor-enfermaria-1`, `sensor-enfermaria-2`, `sensor-enfermaria-3` |
| `triagem` | `10.0.3.0/24` | `gw-triagem` | `sensor-triagem-1`, `sensor-triagem-2`, `sensor-triagem-3` |
| `hospital_core` | `10.0.100.0/24` | gateways e servicos centrais | `server`, `controller`, `dashboard` |

O servidor hospitalar fica em `10.0.100.10:9000`. A API REST fica em `http://localhost:8000`.

## O Que Ja Esta Implementado

- Sensores medicos simulados em Python, com `interval`, `payload_padding_bytes`
  e `enabled` controlaveis em runtime via arquivo `/tmp/sensor_control.json`.
- Servidor hospitalar UDP em Python.
- Gateways VNF com rotas, NAT, encaminhamento IP, `iptables` e `tc`.
- Politicas VNF dinamicas: `tc tbf` parametrizavel (`rate`, `burst`, `latency`),
  `tc netem` parametrizavel (`delay`, `jitter`, `loss`, `duplicate`, `corrupt`,
  `reorder`) e bloqueio da triagem.
- Cenarios nomeados (`normal`, `congestionamento_enfermaria`, `surto_uti`,
  `falha_triagem`) que combinam varias acoes em sequencia.
- Controlador Ryu e topologia Mininet inicial.
- Ambiente Docker Compose com servidor, sensores, gateways, controlador e API.
- API REST FastAPI para status, logs, metricas, diagnostico dos gateways e
  acionamento de politicas, com Swagger em `/docs`.
- Persistencia de snapshots de metricas em SQLite (`/data/metrics.db` via volume
  nomeado `metrics_db`) com task assincrona de ingest no `lifespan` do FastAPI
  e endpoints `/timeseries/*` para consumo por dashboards.
- Documentacao detalhada dos contratos da API em `docs/api.md`.

Ainda estao pendentes para etapas futuras:

- simulacao NS-3;
- coleta organizada de evidencias;
- relatorio tecnico final.

## Estrutura Atual

```text
.
├── apps/
│   ├── sensor_medico.py
│   ├── servidor_hospitalar.py
│   └── Dockerfile
├── controller/
│   ├── ryu_controller.py
│   └── Dockerfile
├── dashboard/
│   ├── app.py
│   ├── ingester.py
│   ├── storage.py
│   ├── requirements.txt
│   └── Dockerfile
├── docs/
│   └── api.md
├── topology/
│   └── hospital_topology.py
├── vnf/
│   ├── aplicar_netem.sh
│   ├── aplicar_tbf.sh
│   ├── bloquear_triagem.sh
│   ├── common.sh
│   ├── gw_enfermaria.sh
│   ├── gw_triagem.sh
│   ├── gw_uti.sh
│   ├── limitar_enfermaria.sh
│   ├── remover_netem.sh
│   ├── remover_tbf.sh
│   ├── restaurar_politicas.sh
│   └── Dockerfile
├── docker-compose.yml
├── estrutura_atividade_6_sdn_nfv_ns3_saude.md
└── plano_de_execucao.md
```

## Requisitos

Para executar o ambiente principal:

- Docker Desktop ou Docker Engine com Docker Compose;
- acesso ao socket Docker, pois a API consulta containers e executa comandos neles.

Para executar a topologia SDN fora do Docker Compose:

- Ryu;
- Mininet;
- Open vSwitch.

## Como Subir a Aplicacao

Subir todos os containers:

```bash
docker compose up -d --build
```

O Compose usa o nome fixo de projeto `atividad_6`. Isso evita que a API marque containers como `missing` quando o repositorio for clonado em uma pasta com outro nome.

Verificar o estado:

```bash
docker compose ps
```

Ver logs do servidor hospitalar:

```bash
docker compose logs -f server
```

Encerrar o ambiente:

```bash
docker compose down
```

## Servicos Docker

| Servico | Funcao |
|---|---|
| `server` | Servidor hospitalar UDP em `10.0.100.10:9000`. |
| `dashboard` | API REST FastAPI publicada em `localhost:8000`. |
| `controller` | Controlador Ryu com portas `6633` e `8080`. |
| `gw-uti` | Gateway VNF da UTI. |
| `gw-enfermaria` | Gateway VNF da enfermaria. |
| `gw-triagem` | Gateway VNF da triagem. |
| `sensor-uti-*` | Sensores simulados da UTI. |
| `sensor-enfermaria-*` | Sensores simulados da enfermaria. |
| `sensor-triagem-*` | Sensores simulados da triagem. |

## API REST

Base URL:

```text
http://localhost:8000
```

Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

Contrato detalhado para integracao com frontend:

```text
docs/api.md
```

## Endpoints Principais

Sistema:

```text
GET /health
GET /status
GET /containers
GET /logs/{container_name}
```

Grupos:

```text
GET /groups
GET /groups/{group}
GET /groups/{group}/sensors
GET /groups/{group}/sensors/metrics
GET /groups/{group}/sensors/{sensor}/metrics
GET /groups/{group}/gateway
GET /groups/{group}/gateway/iptables
GET /groups/{group}/gateway/tc
GET /groups/{group}/gateway/interfaces
GET /groups/{group}/routes
GET /groups/{group}/logs
GET /groups/{group}/metrics
```

Gateways:

```text
GET /gateways
GET /gateways/{gateway}/iptables
GET /gateways/{gateway}/tc
GET /gateways/{gateway}/interfaces
```

Metricas:

```text
GET /metrics/traffic
GET /metrics/traffic/{group}
GET /sensors/metrics
```

Politicas:

```text
GET  /policies
POST /policies/enfermaria/limit
POST /policies/enfermaria/restore
POST /policies/triagem/block
POST /policies/triagem/unblock
POST /policies/restore
POST /policies/{group}/limit            (TBF parametrizado por rate/burst/latency)
POST /policies/{group}/limit/clear
POST /policies/{group}/netem            (netem parametrizado por delay/jitter/loss/...)
POST /policies/{group}/netem/clear
```

Sensores (controle em runtime):

```text
GET  /sensors/{sensor}/config
POST /sensors/{sensor}/config           (body: interval, payload_padding_bytes, enabled)
POST /sensors/{sensor}/start
POST /sensors/{sensor}/stop
```

Cenarios:

```text
GET  /scenarios
POST /scenarios/{name}
```

Series temporais (persistencia SQLite):

```text
GET /timeseries/stats
GET /timeseries/metrics
GET /timeseries/sensors/latest
GET /timeseries/sensors
GET /timeseries/series
```

Rotas de compatibilidade:

```text
GET /sensors
GET /routes/{container_name}
```

## Exemplos de Uso da API

Status geral:

```bash
curl http://localhost:8000/status
```

Listar grupos:

```bash
curl http://localhost:8000/groups
```

Consultar metricas da UTI:

```bash
curl http://localhost:8000/groups/uti/metrics
```

Consultar metricas por sensor da UTI:

```bash
curl http://localhost:8000/groups/uti/sensors/metrics
```

Consultar metricas de um sensor especifico:

```bash
curl http://localhost:8000/groups/uti/sensors/sensor-cardiaco/metrics
```

Consultar status detalhado dos gateways:

```bash
curl http://localhost:8000/gateways
```

Consultar contrato das politicas disponiveis:

```bash
curl http://localhost:8000/policies
```

Aplicar limitacao de banda na enfermaria:

```bash
curl -X POST http://localhost:8000/policies/enfermaria/limit
```

Bloquear trafego da triagem:

```bash
curl -X POST http://localhost:8000/policies/triagem/block
```

Restaurar todas as politicas dinamicas:

```bash
curl -X POST http://localhost:8000/policies/restore
```

Aplicar `tc netem` parametrizado em um grupo:

```bash
curl -X POST http://localhost:8000/policies/triagem/netem \
  -H "Content-Type: application/json" \
  -d '{"delay_ms": 500, "jitter_ms": 100, "loss_pct": 30}'
```

Aplicar limitacao de banda customizada:

```bash
curl -X POST http://localhost:8000/policies/enfermaria/limit \
  -H "Content-Type: application/json" \
  -d '{"rate": "64kbit", "burst": "8kbit", "latency": "200ms"}'
```

Ajustar sensor em runtime (rajada na UTI):

```bash
curl -X POST http://localhost:8000/sensors/sensor-uti-1/config \
  -H "Content-Type: application/json" \
  -d '{"interval": 0.2, "payload_padding_bytes": 2048}'
```

Aplicar um cenario completo:

```bash
curl http://localhost:8000/scenarios
curl -X POST http://localhost:8000/scenarios/surto_uti
curl -X POST http://localhost:8000/scenarios/normal   # reverte qualquer cenario
```

Consultar series temporais persistidas (apos o ingest preencher o SQLite):

```bash
curl http://localhost:8000/timeseries/stats
curl "http://localhost:8000/timeseries/sensors/latest?group=uti"
curl "http://localhost:8000/timeseries/series?metric=avg_delay_ms&group=uti"
```

## Status dos Gateways

`GET /gateways` retorna os gateways por grupo com dados operacionais:

```json
{
  "enfermaria": {
    "group": "enfermaria",
    "container": "gw-enfermaria",
    "docker_status": "running",
    "running": true,
    "image": "atividad_6-gw-enfermaria:latest",
    "id": "18dc4007211e",
    "ip_forward": "1",
    "interfaces": "lo UNKNOWN 127.0.0.1/8 ::1/128\neth0 UP 10.0.2.1/24\neth1 UP 10.0.100.2/24\n",
    "tc_eth1": "qdisc noqueue 0: root refcnt 2 \n",
    "policies": {
      "bandwidth_limit_active": false,
      "triage_block_active": false,
      "network_emulation_active": false
    }
  }
}
```

Campos importantes:

| Campo | Descricao |
|---|---|
| `docker_status` | Estado do container no Docker. |
| `running` | Indica se o gateway esta em execucao. |
| `ip_forward` | Valor de `/proc/sys/net/ipv4/ip_forward` dentro do gateway. |
| `interfaces` | Saida de `ip -br addr`. |
| `tc_eth1` | Saida de `tc qdisc show dev eth1`. |
| `policies.bandwidth_limit_active` | Indica se existe limitacao `tbf` ativa. |
| `policies.triage_block_active` | Indica se existe bloqueio da triagem para o servidor. |
| `policies.network_emulation_active` | Indica se existe `tc netem` ativo (degradacao de rede). |

## Politicas de Rede

Existem dois conjuntos de politicas:

- **Politicas fixas** (`/policies/...`) — acoes sem payload no body, ativadas/
  restauradas com um `POST` simples. Sao as historicas: `enfermaria_limit`,
  `enfermaria_restore`, `triagem_block`, `triagem_unblock`, `restore_all`.
- **Politicas parametrizadas** (`/policies/{group}/limit`,
  `/policies/{group}/netem` e seus `clear`) — aceitam body para configurar
  `tc tbf` e `tc netem` por grupo. Detalhes em "Melhorias em Implementacao".

Para descobrir as fixas, consulte primeiro:

```bash
curl http://localhost:8000/policies
```

Exemplo de item retornado:

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

Fluxo recomendado:

1. Consultar `GET /policies`.
2. Chamar o `POST` indicado no campo `path`.
3. Conferir o resultado operacional pelo `CommandResult.exit_code`.
4. Consultar `GET /gateways` para verificar se a politica ficou ativa.

## Metricas

As metricas de trafego sao calculadas a partir dos logs do servidor hospitalar.

Quando ainda nao existem amostras nos logs, os grupos validos continuam aparecendo com contadores zerados. Isso ajuda o frontend a diferenciar "grupo sem trafego ainda" de "grupo invalido".

Principais campos:

| Campo | Descricao |
|---|---|
| `messages` | Quantidade de mensagens recebidas. |
| `bytes` | Total de bytes processados. |
| `duration_seconds` | Janela temporal observada nos logs. |
| `messages_per_second` | Taxa media de mensagens por segundo. |
| `throughput_bps` | Vazao estimada em bits por segundo. |
| `avg_delay_ms` | Atraso medio calculado pelo timestamp do sensor. |
| `jitter_ms` | Variacao media entre atrasos consecutivos. |
| `packet_loss_percent` | Perda estimada por lacunas na sequencia por origem. |

Metricas por sensor:

```text
GET /sensors/metrics
GET /groups/{group}/sensors/metrics
GET /groups/{group}/sensors/{sensor}/metrics
```

Esses endpoints usam os logs do servidor e nao alteram os contratos antigos. Eles retornam campos como:

| Campo | Descricao |
|---|---|
| `sensor` | Nome do sensor registrado no log, como `sensor-cardiaco`. |
| `origins` | Origens IP:porta que enviaram leituras daquele sensor. |
| `avg_payload_bytes` | Tamanho medio das mensagens do sensor. |
| `min_delay_ms` | Menor atraso observado. |
| `max_delay_ms` | Maior atraso observado. |
| `last_sequence` | Ultima sequencia recebida para o sensor. |
| `last_reading` | Ultima leitura clinica registrada. |
| `reading_stats` | Minimo, maximo, media e ultimo valor por campo numerico da leitura. |

## Diagnostico Manual nos Containers

Ver rotas:

```bash
docker compose exec sensor-uti-1 ip route
docker compose exec server ip route
docker compose exec gw-uti ip route
```

Ver encaminhamento IP:

```bash
docker compose exec gw-uti cat /proc/sys/net/ipv4/ip_forward
```

Ver regras `iptables`:

```bash
docker compose exec gw-triagem iptables -L FORWARD -v -n
```

Ver politicas `tc`:

```bash
docker compose exec gw-enfermaria tc qdisc show dev eth1
```

## Execucao Local Sem Docker

Tambem e possivel executar apenas os scripts Python diretamente para validar sensores e servidor em localhost.

Terminal 1:

```bash
python3 apps/servidor_hospitalar.py --host 127.0.0.1 --port 9000
```

Terminal 2:

```bash
python3 apps/sensor_medico.py --grupo uti --count 3
python3 apps/sensor_medico.py --grupo enfermaria --count 3
python3 apps/sensor_medico.py --grupo triagem --count 3
```

## Topologia SDN com Mininet

A topologia inicial esta em `topology/hospital_topology.py` e o controlador Ryu em `controller/ryu_controller.py`.

Terminal 1:

```bash
ryu-manager controller/ryu_controller.py --ofp-tcp-listen-port 6633
```

Terminal 2:

```bash
sudo python3 topology/hospital_topology.py
```

Validacoes no CLI do Mininet:

```bash
sensor-uti-1 ping -c 2 10.0.100.10
sensor-enfermaria-1 ping -c 2 10.0.100.10
sensor-triagem-1 ping -c 2 10.0.100.10
```

Fluxos OpenFlow:

```bash
ovs-ofctl -O OpenFlow13 dump-flows s1
ovs-ofctl -O OpenFlow13 dump-flows s2
ovs-ofctl -O OpenFlow13 dump-flows s3
ovs-ofctl -O OpenFlow13 dump-flows s4
```

## Melhorias em Implementacao

Esta secao documenta as melhorias **ja implementadas** para dar mais dinamica
visual ao ambiente quando se interage com a API REST. O cenario original
("limitacao" e "bloqueio") mexia com `tc tbf` e `iptables` em valores fixos,
mas o volume de trafego dos sensores (`~150 bytes` a cada `2s`) era ordens de
magnitude menor que o teto de `256kbit` configurado — as metricas nao
apresentavam variacao perceptivel. As melhorias abaixo expoem parametros de
degradacao realista de rede, tornam os sensores controlaveis em runtime e
persistem as metricas para alimentar dashboards. Cada acao da API agora gera
efeito visivel em `avg_delay_ms`, `jitter_ms`, `packet_loss_percent` e
`throughput_bps`.

### 1. Emulacao de Rede com `tc netem`

Novos scripts VNF aplicam `tc netem` por gateway, controlados pela API:

| Parametro | Efeito visivel |
|---|---|
| `delay_ms` | Aumenta `avg_delay_ms` no grupo afetado. |
| `jitter_ms` | Reflete em `jitter_ms` (variacao em torno do delay). |
| `loss_pct` | Aparece em `packet_loss_percent` e em gaps de sequencia. |
| `duplicate_pct` | Mensagens duplicadas no log do servidor. |
| `corrupt_pct` | Mensagens descartadas como JSON invalido. |
| `reorder_pct` | Reordenacao detectavel pelas sequencias por origem. |

Endpoints:

```text
POST /policies/{group}/netem        (body com os campos acima)
POST /policies/{group}/netem/clear
```

### 2. TBF Dinamico

A limitacao de banda passa a aceitar parametros (`rate`, `burst`, `latency`) no
body, em vez do limite fixo de `256kbit`. Permite varrer de `1Mbit` ate `8kbit`
para ver o impacto crescente.

Endpoints:

```text
POST /policies/{group}/limit        (body opcional: rate, burst, latency)
POST /policies/{group}/limit/clear
```

A rota antiga `POST /policies/enfermaria/limit` permanece como atalho.

### 3. Sensores Configuraveis em Runtime

Os sensores passam a ler um arquivo de controle (`/tmp/sensor_control.json`)
a cada ciclo. A API edita esse arquivo via `docker exec`, permitindo:

| Parametro | Efeito |
|---|---|
| `interval` | Tempo entre envios em segundos (ex.: `0.2` para gerar rajada). |
| `payload_padding_bytes` | Bytes extras no payload UDP para inflar o trafego. |
| `enabled` | `false` pausa o envio sem matar o container. |

Endpoints:

```text
GET  /sensors/{name}/config
POST /sensors/{name}/config        (body: interval, payload_padding_bytes, enabled)
POST /sensors/{name}/start         (docker start)
POST /sensors/{name}/stop          (docker stop)
```

### 4. Persistencia de Snapshots (SQLite)

O endpoint `GET /sensors/metrics?tail=1000` entrega um agregado calculado
sob demanda a partir dos logs do servidor. Para alimentar um dashboard com
serie temporal, esse agregado e capturado periodicamente e persistido em
SQLite (`/data/metrics.db`, montado via volume nomeado `metrics_db`).

A captura roda em uma task assincrona dentro do FastAPI (`lifespan`), gerando
uma linha por `(grupo, sensor)` a cada ciclo, com todas as metricas escalares
da resposta original e os campos de shape variavel (`origins`, `last_reading`,
`reading_stats`) serializados como JSON.

Variaveis de ambiente:

| Variavel | Default | Funcao |
|---|---|---|
| `METRICS_DB_PATH` | `/data/metrics.db` | Caminho do arquivo SQLite. |
| `INGEST_INTERVAL_S` | `30` | Intervalo entre capturas. |
| `INGEST_TAIL` | `1000` | Valor de `tail` usado em cada captura. |
| `INGEST_ENABLED` | `true` | Desliga a task se `false`. |

Endpoints disponiveis:

```text
GET /timeseries/stats
GET /timeseries/metrics
GET /timeseries/sensors/latest        (filtros opcionais: group, sensor)
GET /timeseries/sensors               (paginacao por intervalo)
GET /timeseries/series                (serie temporal por metrica)
```

`GET /timeseries/sensors` aceita:

| Parametro | Default | Descricao |
|---|---|---|
| `group` | - | Filtra pelo grupo (`uti`, `enfermaria`, `triagem`). |
| `sensor` | - | Filtra pelo sensor (ex.: `sensor-cardiaco`). |
| `since` | - | Data/hora minima do `captured_at` (ISO 8601). |
| `until` | - | Data/hora maxima do `captured_at` (ISO 8601). |
| `limit` | `200` | Tamanho da pagina (max `2000`). |
| `offset` | `0` | Deslocamento. |
| `order` | `desc` | `asc` ou `desc` por `captured_at`. |

Resposta inclui `total`, `limit`, `offset`, `order` e `items` (cada item e um
`SensorMetricsSnapshot` completo, com os campos JSON desserializados).

`GET /timeseries/series` retorna pontos `{t, v}` por sensor, prontos para
graficos. Parametros:

| Parametro | Default | Descricao |
|---|---|---|
| `metric` | obrigatorio | Nome da metrica (ver `/timeseries/metrics`). |
| `group` | - | Filtra pelo grupo. |
| `sensor` | - | Filtra pelo sensor. |
| `since` | - | Data/hora minima (ISO 8601). |
| `until` | - | Data/hora maxima (ISO 8601). |
| `limit` | `5000` | Maximo de pontos (max `20000`). |

Resposta:

```json
{
  "metric": "avg_delay_ms",
  "since": null,
  "until": null,
  "series": [
    {
      "group": "uti",
      "sensor": "sensor-cardiaco",
      "points": [
        {"t": "2026-05-31T00:00:00+00:00", "v": 0.5},
        {"t": "2026-05-31T00:00:30+00:00", "v": 0.6}
      ]
    }
  ]
}
```

Metricas suportadas (whitelist em `storage.ALLOWED_METRICS`): `messages`,
`bytes`, `duration_seconds`, `messages_per_second`, `throughput_bps`,
`avg_payload_bytes`, `avg_delay_ms`, `min_delay_ms`, `max_delay_ms`,
`jitter_ms`, `expected_messages`, `missing_messages`, `packet_loss_percent`,
`last_sequence`. Valores fora dessa lista retornam `400`.

Exemplos:

```bash
curl http://localhost:8000/timeseries/stats
curl http://localhost:8000/timeseries/metrics

curl http://localhost:8000/timeseries/sensors/latest
curl "http://localhost:8000/timeseries/sensors/latest?group=uti&sensor=sensor-cardiaco"

curl "http://localhost:8000/timeseries/sensors?group=uti&limit=50&order=desc"
curl "http://localhost:8000/timeseries/sensors?since=2026-05-31T00:00:00&until=2026-05-31T01:00:00"

curl "http://localhost:8000/timeseries/series?metric=avg_delay_ms&group=uti"
curl "http://localhost:8000/timeseries/series?metric=throughput_bps&sensor=sensor-cardiaco&since=2026-05-31T00:00:00"
```

Proximas etapas previstas (agregacao por grupo e retencao automatica)
reusam a mesma tabela `sensor_metrics_snapshot`.

### 5. Cenarios Nomeados

Combinacoes pre-definidas de politicas para gerar evidencias e prints
comparaveis. Cada cenario aplica varias acoes em sequencia.

Cenarios iniciais:

| Cenario | O que faz |
|---|---|
| `normal` | Restaura tudo: remove netem, tbf e bloqueios; reseta config dos sensores. |
| `congestionamento_enfermaria` | Aplica `netem delay=200ms jitter=50ms loss=5%` na enfermaria. |
| `surto_uti` | Reduz intervalo dos sensores da UTI para `0.2s` e infla payload em `2048` bytes. |
| `falha_triagem` | Aplica `netem delay=500ms jitter=100ms loss=30%` na triagem. |

Endpoints:

```text
GET  /scenarios
POST /scenarios/{name}
```

## Proximas Etapas

1. Implementar a simulacao NS-3 para comparar cenario normal e cenario com limitacao.
2. Registrar evidencias de execucao: logs, metricas, respostas da API e prints.
3. Consolidar o relatorio tecnico final.
