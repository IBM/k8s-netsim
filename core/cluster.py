"""
A class to represent and manage a Kubernetes cluster.
"""

import time

from .etcd import Etcd
from .worker import Worker

from mininet.log import info

class Cluster():
    def __init__(self, cluster, numworkers=3, etcd_prefix="10.0"):
        self.name = cluster
        self.numworkers = numworkers
        self.etcd_prefix = etcd_prefix
        self.workers = []

    def deriveName(self, item):
        return "C" + self.name + item

    def addTopo(self, topo):
        # Add top level switch
        s0 = topo.addSwitch(self.deriveName('s0'))

        # Add etcd cluster
        # hardcode IPs here so that we can refer to these in Endpoint creation
        cluster = "{0}=http://{2}.0.1:2380,{1}=http://{2}.0.2:2380".format(self.deriveName("e1"), self.deriveName("e2"), self.etcd_prefix)
        e1 = topo.addNode(self.deriveName('e1'), ip='%s.0.1'%self.etcd_prefix, cls=Etcd, cluster=cluster)
        e2 = topo.addNode(self.deriveName('e2'), ip='%s.0.2'%self.etcd_prefix, cls=Etcd, cluster=cluster)

        # Connect etcd nodes to top level
        topo.addLink(e1, s0)
        topo.addLink(e2, s0)

        # Track worker names, just strings for now
        for i in range(self.numworkers):
            w = topo.addNode(self.deriveName('w' + str(i+1)), cls=Worker, etcd='%s.0.1'%self.etcd_prefix, cluster=self.name)
            topo.addLink(w, s0)
            self.workers.append(w)

    def startup(self, net):
        e1 = net.getNodeByName(self.deriveName("e1"))
        e2 = net.getNodeByName(self.deriveName("e2"))

        e1.start()
        e2.start()

        time.sleep(2)
        e1.loadFlannelConf()

        # replace the workers array with actual worker objects
        worker_nodes = []
        for w in self.workers:
            worker_nodes.append(net.getNodeByName(w))
        self.workers = worker_nodes

        for w in self.workers:
            w.start_flannel()

        # wait for flannel configuration to propogate
        time.sleep(1)

        for w in self.workers:
            w.setup_cni()
            w.setup_kp()

    def get(self, name):
        for w in self.workers:
            if w.name == self.deriveName(name):
                return w

        info("Worker with name: %s not found in cluster" % workername)
        return None

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

