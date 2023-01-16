"""
A Node representing a Kubernetes worker.
"""

import os
import json

from mininet.node import Node
from mininet.log import info

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

    def exec_container_async(self, name, cmd):
        self.exec_container(name, "nohup " + cmd + " >&/dev/null &")

    def setup_kp(self):
        # prepare nft chain to be used later
        self.cmd("nft add table ip nat")
        self.cmd("nft add chain nat PREROUTING { type nat hook prerouting priority dstnat\; }")

    def terminate(self):
        # undo things, if needed

        # clean up all containers
        # we need to use a copy, since the delete function manipulates the same list
        for c in self.containers.copy():
            self.delete_container(c)

        super(Worker, self).terminate()
