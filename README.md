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
- painel web simples para politicas e visualizacao;
- simulacao NS-3 com comparacao entre cenario normal e cenario limitado.

## Estrutura do Repositorio

```text
.
├── apps/                 # Sensores simulados e servidor hospitalar
├── controller/           # Controlador SDN Ryu
├── dashboard/            # Painel web e API
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
6. Painel web.
7. Simulacao NS-3.
8. Evidencias.
9. Relatorio tecnico.

## Proxima Etapa

A proxima subtarefa e implementar as aplicacoes basicas:

- servidor hospitalar central;
- sensor medico generico;
- envio de mensagens por grupo: UTI, enfermaria e triagem.
