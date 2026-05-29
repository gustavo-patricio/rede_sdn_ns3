# Plano de Execucao - Atividade 6 SDN/NFV/NS-3

## Objetivo

Construir o trabalho por etapas pequenas, mantendo cada entrega testavel antes de avancar para a proxima.

## Subtarefa 1 - Base do repositorio

Entregas:
- criar estrutura inicial de diretorios;
- separar codigo, simulacao, evidencias e relatorio;
- manter o arquivo original como referencia do projeto.

Criterio de conclusao:
- diretorios principais criados;
- README inicial explicando o objetivo do trabalho.

## Subtarefa 2 - Aplicacoes basicas

Entregas:
- servidor hospitalar central em Python;
- sensor medico generico em Python;
- simulacao dos tres grupos: UTI, enfermaria e triagem.

Criterio de conclusao:
- sensores enviam mensagens;
- servidor recebe e registra dados por grupo.

## Subtarefa 3 - Gateways VNF

Entregas:
- scripts dos gateways `gw-uti`, `gw-enfermaria` e `gw-triagem`;
- script para limitar banda da enfermaria;
- script para bloquear triagem;
- script para restaurar politicas.

Criterio de conclusao:
- comandos `iptables` e `tc` documentados;
- politicas podem ser aplicadas e revertidas.

## Subtarefa 4 - Ambiente SDN

Entregas:
- controlador Ryu;
- topologia com switches OpenFlow;
- integracao com Open vSwitch ou Mininet/Containernet.

Criterio de conclusao:
- switches conectam ao controlador;
- `ovs-ofctl dump-flows` mostra fluxos instalados.

## Subtarefa 5 - Docker Compose

Entregas:
- `docker-compose.yml`;
- containers do controlador, servidor, sensores, gateways e painel;
- configuracao de rede entre os servicos.

Criterio de conclusao:
- `docker compose up -d` sobe o ambiente;
- `docker compose ps` mostra servicos ativos.

## Subtarefa 6 - Painel web

Entregas:
- API simples em Flask ou FastAPI;
- pagina HTML para status e politicas;
- botoes para limitar enfermaria, bloquear triagem e restaurar politicas.

Criterio de conclusao:
- painel abre no navegador;
- acoes do painel executam os scripts de politica.

## Subtarefa 7 - Simulacao NS-3

Entregas:
- simulacao logica do cenario hospitalar;
- cenario normal;
- cenario com limitacao da enfermaria;
- coleta de throughput, delay, packet loss e jitter.

Criterio de conclusao:
- resultados gerados em CSV;
- normal e limitado podem ser comparados.

## Subtarefa 8 - Evidencias

Entregas:
- prints do painel;
- logs do servidor;
- saidas de `ovs-ofctl`, `iptables` e `tc`;
- resultados do NS-3.

Criterio de conclusao:
- pasta `evidencias/` preenchida com imagens ou arquivos de saida.

## Subtarefa 9 - Relatorio tecnico

Entregas:
- relatorio de 5 a 7 paginas;
- descricao da arquitetura;
- explicacao SDN/NFV;
- resultados comparativos;
- conclusao.

Criterio de conclusao:
- relatorio completo em Markdown;
- tabelas e evidencias referenciadas.

## Proxima acao recomendada

Iniciar pela Subtarefa 1:

1. Criar a estrutura de diretorios.
2. Criar um README inicial.
3. Fazer commit da organizacao inicial.
