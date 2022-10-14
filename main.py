#!/usr/bin/env python3

import os

from mininet.net import Mininet
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel, info

from core.cluster import Cluster
from core.skupper import create_conf

class UnderlayTopo(Topo):
    def __init__(self, clusters):
        self.clusters = clusters
        super(UnderlayTopo, self).__init__()

    def build(self):
        for C in self.clusters:
            C.addTopo(self)

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
    os.mkdir("/tmp/knetsim/skupper")
    os.system("cp -r ./conf/ /tmp/knetsim/conf/")

    # Setup LinuxBridge
    os.system('sysctl net.bridge.bridge-nf-call-arptables=0')
    os.system('sysctl net.bridge.bridge-nf-call-iptables=0')
    os.system('sysctl net.bridge.bridge-nf-call-ip6tables=0')

    # TODO: still need to use 10. series, else doesn't work
    C0 = Cluster(cluster="0", numworkers=3, etcd_prefix="10.1")
    C1 = Cluster(cluster="1", numworkers=3, etcd_prefix="10.2")
    topo = UnderlayTopo([C0, C1])

    # Override switch to use the simple LinuxBridge standalone without controller
    # This should not be needed, but the default ovs-testcontroller seems to be broken - aka, ping is not working
    net = Mininet(topo=topo, switch=LinuxBridge, controller=None)
    net.start()

    C0.startup(net)
    C1.startup(net)

    C0.get("w1").create_container("c1")
    C0.get("w2").create_container("c2")
    C0.get("w3").create_container("c3")
    C0.kp_vip_add("100.64.10.1", ["c2", "c3"])

    C1.get("w1").create_container("c1")
    C1.get("w2").create_container("c2")
    C1.get("w3").create_container("c3")
    C1.kp_vip_add("100.64.10.1", ["c2", "c3"])

    # Run a test
    print("Running connectivity test...")
    print(C0.get("w1").exec_container("c1", "ping 100.64.10.1 -c 5"))
    print(C1.get("w1").exec_container("c1", "ping 100.64.10.1 -c 5"))

    # Multi-cluster networking
    create_conf(C0)
    create_conf(C1, [C0])

    CLI(net)

    # don't need to delete_containers manually, since we have a teardown function that does it

    net.stop()
    info("Cleaning up loose ends...\n")
    cleanup()

if __name__ == "__main__":
    main()
