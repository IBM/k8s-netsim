#!/usr/bin/env python3

import logging
import os
import time
import json

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
--data-dir /tmp/knetsim/{0}.etcd
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
        self.containers = []

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

    def _gen_flannel_conf(self):
        conf = {"name": self.name,
                "type": "flannel",
                "subnetFile": "/tmp/knetsim/{0}/flannel-subnet.env".format(self.name),
                "dataDir": "/tmp/knetsim/{0}/flannel".format(self.name)}
        return conf

    def setup_flannel(self):
        # build up the json conf for use at container creation time
        with open("/tmp/knetsim/{0}/flannel_conf.json".format(self.name), "w") as conffile:
            json.dump(self._gen_flannel_conf(), conffile)

    def _container_name(self, name):
        return self.name + name

    def create_container(self, name):
        # 1. Create netns
        self.cmd("ip netns add {0}".format(self._container_name(name)))
        # 2. Run flannel cni in the netns
        cmd = "CNI_PATH=/tmp/knetsim/cni NETCONFPATH=/tmp/knetsim/{0} /tmp/knetsim/cnitool add \"{0}\" /var/run/netns/{1}".format(self.name, self._container_name(name))
        logging.debug(self.cmd(cmd))
        # 3. Add container to list of containers
        self.containers.append(name)

    def delete_container(self, name):
        # 1. Run the cnitool delete command.
        self.cmd("CNI_PATH=/tmp/knetsim/cni NETCONFPATH=/tmp/knetsim/{0} /tmp/knetsim/cnitool del \"{0}\" /var/run/netns/{1}".format(self.name, self._container_name(name)))
        # 2. Delete the netns.
        self.cmd("ip netns del {0}".format(self._container_name(name)))
        # 2. Remove container from list of containers.
        self.containers.remove(name)

    def exec_container(self, name, cmd):
        # enter netns and run command
        print(self.cmd("ip netns exec {0} {1}".format(self._container_name(name), cmd)))

    def terminate(self):
        # undo things, if needed
        # TODO: clean up all containers
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

    w1.start_flannel()
    w2.start_flannel()
    w3.start_flannel()

    # wait for flannel configuration to propogate
    time.sleep(2)

    w1.setup_flannel()
    w2.setup_flannel()
    w3.setup_flannel()

    w1.create_container("c1")
    w1.create_container("c2")
    w2.create_container("c1")

    CLI(net)

    w1.delete_container("c1")
    w1.delete_container("c2")
    w2.delete_container("c1")

    net.stop()
    logging.info("Cleaning up loose ends...")
    cleanup()

if __name__ == "__main__":
    main()
