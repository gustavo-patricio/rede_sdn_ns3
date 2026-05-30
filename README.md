# Rede Hospitalar IoMT com SDN, NFV e NS-3

Projeto da Atividade 6 para estruturar, simular e documentar uma rede hospitalar IoMT com controle SDN, funcoes de rede virtualizadas e avaliacao de desempenho no NS-3.

## Tema

A proposta representa tres setores hospitalares com sensores medicos conectados:

- UTI;
- enfermaria;
- pronto atendimento/triagem.

Cada grupo de sensores deve enviar dados para um servidor hospitalar central passando obrigatoriamente por um gateway VNF especifico.

## Objetivo

Implementar e validar um ambiente integrado contendo:

- controlador SDN com switches OpenFlow;
- tres gateways VNF;
- sensores medicos simulados;
- servidor hospitalar central;
- API REST para politicas, visualizacao e diagnostico;
- simulacao NS-3 com comparacao entre cenario normal e cenario limitado.

## Estrutura do Repositorio

```text
.
├── apps/                 # Sensores simulados e servidor hospitalar
├── controller/           # Controlador SDN Ryu
├── dashboard/            # API REST FastAPI para operacao e diagnostico
├── evidencias/           # Prints, logs e saidas usadas no relatorio
├── ns3/                  # Codigo e resultados da simulacao NS-3
├── relatorio/            # Relatorio tecnico
├── topology/             # Topologia Mininet/Containernet
├── vnf/                  # Scripts dos gateways e politicas NFV
├── estrutura_atividade_6_sdn_nfv_ns3_saude.md
└── plano_de_execucao.md
```

## Subtarefas

O desenvolvimento sera feito em etapas:

1. Base do repositorio.
2. Aplicacoes basicas: sensores e servidor.
3. Gateways VNF.
4. Ambiente SDN.
5. Docker Compose.
6. API REST de operacao e diagnostico.
7. Simulacao NS-3.
8. Evidencias.
9. Relatorio tecnico.

## Status Atual

Subtarefas implementadas ate agora:

- base do repositorio;
- aplicacoes basicas com sensores e servidor;
- scripts VNF para gateways e politicas;
- controlador Ryu e topologia Mininet inicial.
- Docker Compose com controlador, servidor, sensores e gateways.
- API REST FastAPI para diagnostico e politicas.

## Executar Subtarefa 2

Em um terminal, iniciar o servidor:

```bash
python3 apps/servidor_hospitalar.py --host 127.0.0.1 --port 9000
```

Em outro terminal, enviar leituras simuladas:

```bash
python3 apps/sensor_medico.py --grupo uti --count 3
python3 apps/sensor_medico.py --grupo enfermaria --count 3
python3 apps/sensor_medico.py --grupo triagem --count 3
```

O servidor deve exibir mensagens recebidas dos tres grupos.

## Executar Subtarefa 3

Os scripts VNF ficam em `vnf/` e devem ser executados dentro do respectivo gateway/container com privilegios de rede.

Preparar gateways:

```bash
sudo ./vnf/gw_uti.sh
sudo ./vnf/gw_enfermaria.sh
sudo ./vnf/gw_triagem.sh
```

Aplicar e reverter politicas:

```bash
sudo ./vnf/limitar_enfermaria.sh
sudo ./vnf/bloquear_triagem.sh
sudo ./vnf/restaurar_politicas.sh
```

Variaveis uteis para adaptar ao ambiente:

```bash
SERVER_IP=10.0.100.10
UTI_NET=10.0.1.0/24
ENFERMARIA_NET=10.0.2.0/24
TRIAGEM_NET=10.0.3.0/24
WAN_IFACE=eth1
LIMIT_RATE=256kbit
```

Validacao esperada:

```bash
sudo iptables -L -v -n
sudo tc qdisc show dev eth1
```

## Executar Subtarefa 4

Dependencias esperadas no ambiente:

```bash
ryu-manager
mininet
openvswitch-switch
```

Terminal 1: iniciar o controlador Ryu:

```bash
ryu-manager controller/ryu_controller.py --ofp-tcp-listen-port 6633
```

Terminal 2: iniciar a topologia Mininet:

```bash
sudo python3 topology/hospital_topology.py
```

Dentro do CLI do Mininet, validar conectividade passando pelos gateways:

```bash
sensor-uti-1 ping -c 2 10.0.100.10
sensor-enfermaria-1 ping -c 2 10.0.100.10
sensor-triagem-1 ping -c 2 10.0.100.10
```

Validar fluxos OpenFlow:

```bash
ovs-ofctl -O OpenFlow13 dump-flows s1
ovs-ofctl -O OpenFlow13 dump-flows s2
ovs-ofctl -O OpenFlow13 dump-flows s3
ovs-ofctl -O OpenFlow13 dump-flows s4
```

Validar rotas:

```bash
sensor-uti-1 ip route
server ip route
gw-uti sysctl net.ipv4.ip_forward
```

## Executar Subtarefa 5

Subir todos os containers:

```bash
docker compose up -d --build
```

Verificar containers:

```bash
docker compose ps
```

Ver logs do servidor hospitalar:

```bash
docker compose logs -f server
```

Validar rotas dentro dos containers:

```bash
docker compose exec sensor-uti-1 ip route
docker compose exec server ip route
docker compose exec gw-uti sysctl net.ipv4.ip_forward
```

Aplicar limitacao no gateway da enfermaria:

```bash
docker compose exec gw-enfermaria bash -lc 'WAN_IFACE=eth1 /opt/vnf/limitar_enfermaria.sh'
docker compose exec gw-enfermaria tc qdisc show dev eth1
```

Bloquear triagem:

```bash
docker compose exec gw-triagem bash -lc '/opt/vnf/bloquear_triagem.sh'
docker compose exec gw-triagem iptables -L FORWARD -v -n
```

Restaurar politicas:

```bash
docker compose exec gw-enfermaria bash -lc 'WAN_IFACE=eth1 /opt/vnf/restaurar_politicas.sh'
docker compose exec gw-triagem bash -lc '/opt/vnf/restaurar_politicas.sh'
```

Encerrar ambiente:

```bash
docker compose down
```

## Executar Subtarefa 6

A API REST fica disponivel em:

```text
http://localhost:8000
http://localhost:8000/docs
```

Endpoints principais:

```text
GET  /health
GET  /status
GET  /containers
GET  /logs/server
GET  /sensors
GET  /gateways
GET  /gateways/{gateway}/iptables
GET  /gateways/{gateway}/tc
GET  /gateways/{gateway}/interfaces
GET  /routes/{container_name}

POST /policies/enfermaria/limit
POST /policies/enfermaria/restore
POST /policies/triagem/block
POST /policies/triagem/unblock
POST /policies/restore
```

Exemplos com `curl`:

```bash
curl http://localhost:8000/status
curl http://localhost:8000/logs/server
curl -X POST http://localhost:8000/policies/enfermaria/limit
curl -X POST http://localhost:8000/policies/triagem/block
curl -X POST http://localhost:8000/policies/restore
```
