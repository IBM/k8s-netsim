#!/usr/bin/env python3

import logging
import os

from mininet.net import Mininet
from mininet.node import Node
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink

class Etcd(Node):
    def config(self, **params):
        super(Etcd, self).config(**params)
        self.cluster = params["cluster"]

    def start(self):
        cmd_t = """nohup /tmp/knetsim/etcd
--name {0}
--initial-advertise-peer-urls http://{1}:2380
--listen-peer-urls http://{1}:2380
--listen-client-urls http://{1}:2379,http://127.0.0.1:2379
--advertise-client-urls http://{1}:2379
--initial-cluster-token etcd-cluster
--initial-cluster {2}
--initial-cluster-state new &""".replace("\n", " ")

        cmd = cmd_t.format(self.name, self.IP(), self.cluster)
        print(cmd)
        self.cmd(cmd)
        self.waitOutput()

    def terminate(self):
        # undo things, if needed
        super(Etcd, self).terminate()

class UnderlayTopo(Topo):
    def build(self):
        # Add top level switch
        s0 = self.addSwitch('s0')

        # Add etcd cluster
        # hardcode IPs here so that we can refer to these in Endpoint creation
        cluster = "e1=http://10.0.0.1:2380,e2=http://10.0.0.2:2380"
        e1 = self.addNode('e1', ip='10.0.0.1', cls=Etcd, cluster=cluster)
        e2 = self.addNode('e2', ip='10.0.0.2', cls=Etcd, cluster=cluster)

        # Connect etcd nodes to top level
        self.addLink(e1, s0)
        self.addLink(e2, s0)

def cleanup():
    # stop running processes
    os.system("killall -9 etcd")
    # clean up config folder
    os.system("rm -rf /tmp/knetsim/")

def main():
    logging.basicConfig(level=logging.DEBUG)

    # prepare configuration dir somewhere which is accessible
    os.system("cp -r ./bin/ /tmp/knetsim/")

    # Setup LinuxBridge
    os.system('sysctl net.bridge.bridge-nf-call-arptables=0')
    os.system('sysctl net.bridge.bridge-nf-call-iptables=0')
    os.system('sysctl net.bridge.bridge-nf-call-ip6tables=0')

    # Override switch to use the simple LinuxBridge standalone without controller
    # This should not be needed, but the default ovs-testcontroller seems to be broken - aka, ping is not working
    net = Mininet(topo=UnderlayTopo(), switch=LinuxBridge, controller=None)
    net.start()

    e1 = net.getNodeByName("e1")
    e2 = net.getNodeByName("e2")

    e1.start()
    e2.start()

    CLI(net)

    net.stop()
    logging.info("Cleaning up loose ends...")
    cleanup()

if __name__ == "__main__":
    main()
