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

- Sensores medicos simulados em Python.
- Servidor hospitalar UDP em Python.
- Gateways VNF com rotas, NAT, encaminhamento IP, `iptables` e `tc`.
- Politicas VNF para limitar banda da enfermaria e bloquear trafego da triagem.
- Controlador Ryu e topologia Mininet inicial.
- Ambiente Docker Compose com servidor, sensores, gateways, controlador e API.
- API REST FastAPI para status, logs, metricas, diagnostico dos gateways e acionamento de politicas.
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
│   ├── requirements.txt
│   └── Dockerfile
├── docs/
│   └── api.md
├── topology/
│   └── hospital_topology.py
├── vnf/
│   ├── bloquear_triagem.sh
│   ├── common.sh
│   ├── gw_enfermaria.sh
│   ├── gw_triagem.sh
│   ├── gw_uti.sh
│   ├── limitar_enfermaria.sh
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
```

Politicas:

```text
GET  /policies
POST /policies/enfermaria/limit
POST /policies/enfermaria/restore
POST /policies/triagem/block
POST /policies/triagem/unblock
POST /policies/restore
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
      "triage_block_active": false
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

## Politicas de Rede

As politicas atuais sao acoes fixas e nao exigem payload no body. Para integrar com frontend, consulte primeiro:

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

## Proximas Etapas

1. Implementar a simulacao NS-3 para comparar cenario normal e cenario com limitacao.
2. Registrar evidencias de execucao: logs, metricas, respostas da API e prints.
3. Consolidar o relatorio tecnico final.
