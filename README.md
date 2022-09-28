# knetsim

## Setup

### Setup prereqs

1. Mininet

### Setup folder

1. Ensure that the following binaries are in the `./bin` folder: `etcd`, `etcdctl`, `flanneld`, `cnitool`.
2. Ensure that the `./bin/cni` directory has the following cni-plugin binaries: `bridge`, `host-local`, `flannel`.

## Troubleshooting

### Check if etcd cluster is healthy

```
mininet> e1 /tmp/knetsim/etcdctl cluster-health
```

Output should be of the form:
```
member 3ebc01aec68d6d70 is healthy: got healthy result from http://10.0.0.1:2379
member ee274cacce804b21 is healthy: got healthy result from http://10.0.0.2:2379
cluster is healthy
```

### Check if flannel is running

```
mininet> w1 ifconfig
```

Output should include a flannel configured tunnel interface:
```
flannel.100: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1450
        inet 11.13.0.0  netmask 255.0.0.0  broadcast 0.0.0.0
        inet6 fe80::90f5:b4ff:feff:aa8c  prefixlen 64  scopeid 0x20<link>
        ether 92:f5:b4:ff:aa:8c  txqueuelen 0  (Ethernet)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 10 overruns 0  carrier 0  collisions 0
```

### Check flannel powered connectivity between containers

```
mininet> py w1.exec_container("c1", "ifconfig")
mininet> py w1.exec_container("c2", "ifconfig")
mininet> py w2.exec_container("c1", "ifconfig")
```

Note the various IPs. Now, try ping tests:

```
mininet> py w1.exec_container("c1", "ping <ip> -c 5")
```
Feed the ip of either another container on the same host, or a container on another host.

Note: `exec_container` function only returns output after the command has completed, so you need to run time-bounded commands there.

