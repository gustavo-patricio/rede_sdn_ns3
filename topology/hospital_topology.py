#!/usr/bin/env python3
"""Topologia Mininet para a rede hospitalar IoMT."""

from __future__ import annotations

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.topo import Topo


class HospitalTopo(Topo):
    """Tres grupos de sensores, tres gateways VNF e um servidor central."""

    def build(self):
        s_uti = self.addSwitch("s1", protocols="OpenFlow13")
        s_enfermaria = self.addSwitch("s2", protocols="OpenFlow13")
        s_triagem = self.addSwitch("s3", protocols="OpenFlow13")
        s_core = self.addSwitch("s4", protocols="OpenFlow13")

        server = self.addHost("server", ip="10.0.100.10/24")

        gw_uti = self.addHost("gw-uti")
        gw_enfermaria = self.addHost("gw-enfermaria")
        gw_triagem = self.addHost("gw-triagem")

        sensors = {
            s_uti: [
                ("sensor-uti-1", "10.0.1.11/24", "10.0.1.1"),
                ("sensor-uti-2", "10.0.1.12/24", "10.0.1.1"),
                ("sensor-uti-3", "10.0.1.13/24", "10.0.1.1"),
            ],
            s_enfermaria: [
                ("sensor-enfermaria-1", "10.0.2.11/24", "10.0.2.1"),
                ("sensor-enfermaria-2", "10.0.2.12/24", "10.0.2.1"),
                ("sensor-enfermaria-3", "10.0.2.13/24", "10.0.2.1"),
            ],
            s_triagem: [
                ("sensor-triagem-1", "10.0.3.11/24", "10.0.3.1"),
                ("sensor-triagem-2", "10.0.3.12/24", "10.0.3.1"),
                ("sensor-triagem-3", "10.0.3.13/24", "10.0.3.1"),
            ],
        }

        for switch, hosts in sensors.items():
            for name, ip_address, gateway in hosts:
                host = self.addHost(name, ip=ip_address, defaultRoute=f"via {gateway}")
                self.addLink(host, switch)

        self.addLink(
            gw_uti,
            s_uti,
            intfName1="gw-uti-eth0",
            params1={"ip": "10.0.1.1/24"},
        )
        self.addLink(
            gw_uti,
            s_core,
            intfName1="gw-uti-eth1",
            params1={"ip": "10.0.100.1/24"},
        )

        self.addLink(
            gw_enfermaria,
            s_enfermaria,
            intfName1="gw-enfermaria-eth0",
            params1={"ip": "10.0.2.1/24"},
        )
        self.addLink(
            gw_enfermaria,
            s_core,
            intfName1="gw-enfermaria-eth1",
            params1={"ip": "10.0.100.2/24"},
        )

        self.addLink(
            gw_triagem,
            s_triagem,
            intfName1="gw-triagem-eth0",
            params1={"ip": "10.0.3.1/24"},
        )
        self.addLink(
            gw_triagem,
            s_core,
            intfName1="gw-triagem-eth1",
            params1={"ip": "10.0.100.3/24"},
        )

        self.addLink(server, s_core)


def enable_gateway_forwarding(net: Mininet) -> None:
    for gateway in ("gw-uti", "gw-enfermaria", "gw-triagem"):
        host = net.get(gateway)
        host.cmd("sysctl -w net.ipv4.ip_forward=1")


def configure_server_routes(net: Mininet) -> None:
    server = net.get("server")
    server.cmd("ip route add 10.0.1.0/24 via 10.0.100.1")
    server.cmd("ip route add 10.0.2.0/24 via 10.0.100.2")
    server.cmd("ip route add 10.0.3.0/24 via 10.0.100.3")


def show_summary(net: Mininet) -> None:
    info("\n*** Enderecos principais\n")
    for name in ("server", "gw-uti", "gw-enfermaria", "gw-triagem"):
        host = net.get(name)
        info(f"{name}: {host.cmd('ip -br addr').strip()}\n")

    info("\n*** Comandos uteis\n")
    info("server python3 apps/servidor_hospitalar.py --host 10.0.100.10 --port 9000\n")
    info("sensor-uti-1 python3 apps/sensor_medico.py --grupo uti --host 10.0.100.10 --count 3\n")
    info("ovs-ofctl -O OpenFlow13 dump-flows s1\n")
    info("ovs-ofctl -O OpenFlow13 dump-flows s4\n\n")


def run() -> None:
    topo = HospitalTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=True,
    )
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)

    info("*** Iniciando rede hospitalar\n")
    net.start()

    enable_gateway_forwarding(net)
    configure_server_routes(net)
    show_summary(net)

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
