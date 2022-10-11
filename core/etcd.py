"""
A Node forming an Etcd cluster
"""

from mininet.node import Node

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
