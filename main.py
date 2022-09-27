#!/usr/bin/env python3

import logging
import os
import time

from mininet.net import Mininet
from mininet.node import Node
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink

from dotenv import dotenv_values

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
--initial-cluster-state new > /tmp/knetsim/{0}.log &""".replace("\n", " ")

        cmd = cmd_t.format(self.name, self.IP(), self.cluster)
        self.cmd(cmd)
        self.waitOutput()

    def loadFlannelConf(self):
        cmd = "/tmp/knetsim/etcdctl set /coreos.com/network/config < /tmp/knetsim/conf/flannel-network-config.json"
        self.cmd(cmd)
        self.waitOutput()

    def terminate(self):
        # undo things, if needed
        super(Etcd, self).terminate()

class Worker(Node):
    def config(self, **params):
        super(Worker, self).config(**params)
        self.etcd = params["etcd"]

        # make a working dir for all worker flags etc
        os.mkdir("/tmp/knetsim/"+self.name)

    def start_flannel(self):
        cmd_t = """nohup /tmp/knetsim/flanneld
-iface={0}
-etcd-endpoints "http://{1}:2379"
-subnet-file /tmp/knetsim/{2}/flannel-subnet.env
> /tmp/knetsim/{2}/flannel.log &""".replace("\n", " ")
        cmd = cmd_t.format(self.IP(), self.etcd, self.name)

        self.cmd(cmd)
        self.waitOutput()

    def start_containerd(self):
        cmd_t = """nohup /tmp/knetsim/containerd
--config=/tmp/knetsim/conf/containerd-config.toml
--root=/tmp/knetsim/{0}/root
--state=/tmp/knetsim/{0}/state
--address=/tmp/knetsim/{0}/grpc.sock
> /tmp/knetsim/{0}/containerd.log &""".replace("\n", " ")
        cmd = cmd_t.format(self.name)

        self.cmd(cmd)
        self.waitOutput()

    def start_docker(self):
       fc = dotenv_values("/tmp/knetsim/"+self.name+"/flannel-subnet.env")

#--bridge=kns{0}d
#ip link add name kns{0}d type bridge;
#ip addr add {1} dev kns{0}d;
#ip link set dev kns{0}d up;

       cmd_t = """
nohup dockerd
--data-root=/tmp/knetsim/{0}/docker-data
--exec-root=/tmp/knetsim/{0}/docker-exec
--host=unix:///tmp/knetsim/{0}/docker.socket
--containerd=/tmp/knetsim/{0}/grpc.sock
--cgroup-parent={0}
--pidfile=/tmp/knetsim/{0}/docker.pid
--bip={1}
--mtu={2}
> /tmp/knetsim/{0}/docker.log &
""".replace("\n", " ")
       cmd = cmd_t.format(self.name, fc["FLANNEL_SUBNET"], fc["FLANNEL_MTU"])

       print(cmd)
       self.cmd(cmd)
       self.waitOutput()

    def start(self):
        self.start_flannel()
        #self.start_containerd()
        # give time for flannel to prepare the subnet files
        time.sleep(2)
        #self.start_docker()

    def terminate(self):
        # undo things, if needed
        super(Worker, self).terminate()

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

        # Add worker nodes
        w1 = self.addNode('w1', cls=Worker, etcd='10.0.0.1')
        w2 = self.addNode('w2', cls=Worker, etcd='10.0.0.1')
        w3 = self.addNode('w3', cls=Worker, etcd='10.0.0.1')

        # connect workers to top level
        self.addLink(w1, s0)
        self.addLink(w2, s0)
        self.addLink(w3, s0)

def cleanup():
    # stop running processes
    os.system("pkill -f .*knetsim.*")
    os.system("killall -9 etcd flanneld")
    # clean up config folder
    os.system("rm -rf /tmp/knetsim/")

def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Cleaning up prev run stragglers...")
    cleanup()

    # prepare configuration dir somewhere which is accessible
    os.system("cp -r ./bin/ /tmp/knetsim/")
    os.system("cp -r ./conf/ /tmp/knetsim/conf/")

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

    e1.loadFlannelConf()

    w1 = net.getNodeByName("w1")
    w2 = net.getNodeByName("w2")
    w3 = net.getNodeByName("w3")

    w1.start()
    w2.start()
    w3.start()

    CLI(net)

    net.stop()
    logging.info("Cleaning up loose ends...")
    cleanup()

if __name__ == "__main__":
    main()
