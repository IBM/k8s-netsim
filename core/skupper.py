"""
Skupper configurator.
"""

import json

def load_base_conf(basefile):
    with open(basefile, "r") as baseconf:
        return json.load(baseconf)

"""
Build a single conf file with all required sections.

Remotes is an array of other clusters.
Svcs is an array of dicts of the following format:
{
  "name": "svc1",   # name of the service - only used for bookkeeping
  "cluster": "0",   # id of the cluster this service is running in
  "host": <ip>,     # ip of the service, usually a container ip
  "port": "80",     # port where the service is running
  "lport": 1028     # port which should be used to expose the service on skupper
}
Note that we use tcpListener and tcpConnectors for services, so only tcp based svcs can be used. HTTP services work fine on this, that is, you don't need the http* versions.

In reality, services can come and go. But, for simplicity of configuration, we require all services to be specified up front, before starting up skupper.
"""
def build_conf(cluster, remotes=[], svcs=[]):
    conf = []

    conf.append(["router",
                 { "id": cluster.name,
                   "mode": "interior",
                   "helloMaxAgeSeconds": "3",
                   "metadata": str({
                       "id": cluster.name,
                       "version": "1.0.2"
                   })
                  }])

    conf += load_base_conf("./conf/skupper_base.json")

    for r in remotes:
        link = ["connector", {
            "name": r.name,
            "role": "inter-router",
            "host": r.get_skupper_host(),
            "port": "55671",
            "cost": 1,
            "maxFrameSize": 16384,
            "maxSessionFrames": 640
        }]
        conf.append(link)

    for svc in svcs:
        # basis of the entry
        entry_core = {
                "name": svc["name"],
                "address": svc["name"],
                "siteId": cluster.name
        }
        if svc["cluster"] == cluster.name:
            # this svc is in this cluster, so create a connector
            entry_core["host"] = svc["host"]
            entry_core["port"] = svc["port"]
            entry = ["tcpConnector", entry_core]
        else :
            # create listeners everywhere else
            entry_core["port"] = svc["lport"]
            entry = ["tcpListener", entry_core]

        conf.append(entry)

    return conf

def create_conf(cluster, remotes=[], svcs=[]):
    with open("/tmp/knetsim/skupper/{0}.json".format(cluster.name), "w") as conffile:
        conf = build_conf(cluster, remotes, svcs)
        json.dump(conf, conffile)
