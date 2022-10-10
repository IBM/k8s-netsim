#!/usr/bin/env python3

import os
import time
import json

from mininet.net import Mininet
from mininet.node import Node
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel, info

class Etcd(Node):
    def config(self, **params):
        super(Etcd, self).config(**params)
        self.cluster = params["cluster"]

    def start(self):
        cmd_t = """nohup etcd
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
        cmd = "etcdctl set /coreos.com/network/config < /tmp/knetsim/conf/flannel-network-config.json"
        self.cmd(cmd)
        self.waitOutput()

    def terminate(self):
        # undo things, if needed
        super(Etcd, self).terminate()

class Worker(Node):
    def config(self, **params):
        super(Worker, self).config(**params)
        self.etcd = params["etcd"]
        self.cluster = params["cluster"]
        self.containers = []

        # make a working dir for all worker flags etc
        os.mkdir("/tmp/knetsim/"+self.name)

    def start_flannel(self):
        cmd_t = """nohup flanneld
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
                "dataDir": "/tmp/knetsim/{0}/flannel".format(self.name),
                "delegate": {
                    "isDefaultGateway": True
                }
        }
        return conf

    def setup_cni(self):
        # build up the json conf for use at container creation time
        with open("/tmp/knetsim/{0}/flannel_conf.json".format(self.name), "w") as conffile:
            json.dump(self._gen_flannel_conf(), conffile)

    def _container_name(self, name):
        return "k" + self.cluster + "_" + name

    def create_container(self, name):
        # 0. Remove old netns, if exists. This shouldn't happen - but just for safety
        self.cmd("ip netns del {0}".format(self._container_name(name)))
        # 1. Create netns
        self.cmd("ip netns add {0}".format(self._container_name(name)))
        # 2. Run flannel cni in the netns
        cmd = "CNI_PATH=/opt/cni/bin NETCONFPATH=/tmp/knetsim/{0} cnitool add \"{0}\" /var/run/netns/{1}".format(self.name, self._container_name(name))
        info(self.cmd(cmd))
        # 3. Add container to list of containers
        self.containers.append(name)

    def delete_container(self, name):
        # 1. Run the cnitool delete command.
        self.cmd("CNI_PATH=/opt/cni/bin NETCONFPATH=/tmp/knetsim/{0} cnitool del \"{0}\" /var/run/netns/{1}".format(self.name, self._container_name(name)))
        # 2. Delete the netns.
        self.cmd("ip netns del {0}".format(self._container_name(name)))
        # 2. Remove container from list of containers.
        self.containers.remove(name)

    def exec_container(self, name, cmd):
        # enter netns and run command
        return self.cmd("ip netns exec {0} {1}".format(self._container_name(name), cmd))

    def setup_kp(self):
        """Any prereq setup to enable kube-proxy.

        We assume flannel has already setup by this time. This is super important - if this order is not followed, things won't work correctly.
        """
        self.cmd("nft add chain nat PREROUTING { type nat hook prerouting priority dstnat\; }")

    def terminate(self):
        # undo things, if needed

        # clean up all containers
        # we need to use a copy, since the delete function manipulates the same list
        for c in self.containers.copy():
            self.delete_container(c)

        super(Worker, self).terminate()

class Cluster():
    def __init__(self, cluster, workers):
        self.name = cluster
        self.workers = workers

    def kp_vip_add(self, vip, containers):
        """
        The required nft rule looks like this:
        nft add rule ip nat PREROUTING ip daddr 100.64.10.1 dnat to numgen inc mod 2 map {0: 11.11.0.2, 1: 11.15.48.2 }
        This causes a dnat load-balanced round-robin between the provided ips, 2 in this case.

        This rule is specific to the chain manually created in the worker using the setup_kp function. This also assumes that the container is setup with a default route to forward to host. This is only achieved with Flannel using isDefaultGateway parameter set to True to be passed onto the bridge cni plugin.
        """

        # 1. Lookup ips of all given containers
        ips = []
        # for each container
        for c in containers:
            # iterate over the workers that make the cluster
            for w in self.workers:
                # if this worker hosts this container
                if c in w.containers:
                    # run local hostname lookup and add the obtained ip
                    ips.append(w.exec_container(c, "hostname -I").split()[0])
                    break
        info("Looking up ips of containers: %s\n" % ips)

        # 2. Generate nft rules to be programmed
        nft_map = ""
        for idx, ip in enumerate(ips):
            if idx != 0:
                nft_map += ", "
            nft_map += "{0}: {1}".format(idx, ip)
        # triple curly bracked needed since we need one actual curly bracket in the output
        nft_cmd = "nft add rule ip nat PREROUTING ip daddr {0} counter dnat to numgen inc mod {1} map {{{2}}}".format(vip, len(ips), nft_map)
        info("Generated nft command: %s\n" % nft_cmd)

        # 3. Run the nft rules on all local workers
        for w in self.workers:
            info("Running nft cmd on %s: %s\n" % (w, w.cmd(nft_cmd)))

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
        w1 = self.addNode('w1', cls=Worker, etcd='10.0.0.1', cluster='0')
        w2 = self.addNode('w2', cls=Worker, etcd='10.0.0.1', cluster='0')
        w3 = self.addNode('w3', cls=Worker, etcd='10.0.0.1', cluster='0')

        # connect workers to top level
        self.addLink(w1, s0)
        self.addLink(w2, s0)
        self.addLink(w3, s0)

def cleanup():
    # stop running processes
    os.system("killall -9 etcd flanneld")
    # clean up config folder
    os.system("rm -rf /tmp/knetsim/")

def main():
    setLogLevel('info')

    info("Cleaning up prev run stragglers...")
    cleanup()

    # prepare configuration dir somewhere which is accessible
    os.system("mkdir /tmp/knetsim/")
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

    time.sleep(2)
    e1.loadFlannelConf()

    w1 = net.getNodeByName("w1")
    w2 = net.getNodeByName("w2")
    w3 = net.getNodeByName("w3")

    w1.start_flannel()
    w2.start_flannel()
    w3.start_flannel()

    # wait for flannel configuration to propogate
    time.sleep(1)

    w1.setup_cni()
    w2.setup_cni()
    w3.setup_cni()

    w1.create_container("c1")
    w2.create_container("c2")
    w3.create_container("c3")

    w1.setup_kp()
    w2.setup_kp()
    w3.setup_kp()

    c0 = Cluster(cluster="0", workers=[w1, w2, w3])
    c0.kp_vip_add("100.64.10.1", ["c2", "c3"])

    # Run a test
    print("Running connectivity test...")
    print(w1.exec_container("c1", "ping 100.64.10.1 -c 5"))

    CLI(net)

    # don't need to delete_containers manually, since we have a teardown function that does it

    net.stop()
    info("Cleaning up loose ends...\n")
    cleanup()

if __name__ == "__main__":
    main()
