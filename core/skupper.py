"""
Skupper configurator.
"""

import json

def load_base_conf(basefile):
    with open(basefile, "r") as baseconf:
        return json.load(baseconf)

"""
Each remote is a dict as follows
{
  "name": <cluster name of remote>,
  "host": <ip of the host running the remote skupper>
}
"""
def build_conf(clustername, remotes=[]):
    conf = []

    conf.append(["router",
                 { "id": clustername,
                   "mode": "interior",
                   "helloMaxAgeSeconds": "3",
                   "metadata": str({
                       "id": clustername,
                       "version": "1.0.2"
                   })
                  }])

    conf.append(load_base_conf("./conf/skupper_base.json"))

    for r in remotes:
        link = ["connector", {
            "name": r["name"],
            "role": "inter-router",
            "host": r["host"],
            "port": "55671",
            "cost": 1,
            "maxFrameSize": 16384,
            "maxSessionFrames": 640
        }]
        conf.append(link)

    return conf

def create_conf(clustername, remotes=[]):
    with open("/tmp/knetsim/skupper/{0}.json".format(clustername), "w") as conffile:
        conf = build_conf(clustername, remotes)
        json.dump(conf, conffile)
