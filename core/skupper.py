"""
Skupper configurator.
"""

import json

def load_base_conf(basefile):
    with open(basefile, "r") as baseconf:
        return json.load(baseconf)

"""
Remotes is an array of other clusters
"""
def build_conf(cluster, remotes=[]):
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

    return conf

def create_conf(cluster, remotes=[]):
    with open("/tmp/knetsim/skupper/{0}.json".format(cluster.name), "w") as conffile:
        conf = build_conf(cluster, remotes)
        json.dump(conf, conffile)
