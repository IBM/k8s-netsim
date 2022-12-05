# knetsim

![Architecture Schema](./imgs/schema.png)

## What?

A simulation of Kubernetes networking using mininet for learning and prototype purposes.

1. Simulate k8s workers as Mininet hosts.
2. Simulate pods/containers as network namespaces inside these workers.
3. Achieve pod-pod connectivity using a real Flannel setup.
4. Achieve pod-service connectivity, ie "kube-proxy" features using nftables.

Additionally, it now also has:

1. Skupper powered multi-cluster container connectivity.

## Running

Make the Docker image:
```
sudo docker build -t knetsim -f ./Dockerfile .
```

Run:
```
docker run -i --privileged --rm knetsim
```

## Presentation:

To preview:
```
marp -p ./presentation/presentation.md
```

## Checking

### Check flannel powered connectivity between containers

```
mininet> py C0w1.exec_container("c1", "ifconfig")
mininet> py C0w2.exec_container("c2", "ifconfig")
mininet> py C0w3.exec_container("c3", "ifconfig")
```

Note the various IPs. Now, try ping tests:

```
mininet> py C0w1.exec_container("c1", "ping <ip> -c 5")
```
Feed the ip of either another container on the same host, or a container on another host.

Note: `exec_container` function only returns output after the command has completed, so you need to run time-bounded commands there.

### Check Kube-Proxy powered connectivity between containers

In the code, we have setup a sample service entry:
```
C0.kp_vip_add("100.64.10.1", ["c2", "c3"])
```

Now, this means that you can ping and reach the 2 containers using this VIP.

```
> py C0w1.exec_container("c1", "ping 100.64.10.1 -c 5")
```

Check the nft counters on the worker:
```
> C0w1 nft list ruleset
```

You can check the load-balancing effect using something like the following. Destroy the container c3 using the command:
```
> py C0w3.delete_container("c3")
```
Now, if you keep running the ping command, you will notice that it fails every other time.

### Check Skupper powered multi-cluster connectivity

In the code, a simple http server is run on a container `c4` on `w3` of the first cluster `C0`. Skupper is configured to expose this service to the other cluster `C1` on `C1w1:1028`.

Note down the IP of the worker where Skupper Router is running on C1, it is "w1" with ip `10.0.0.8` in the example below.

Try the following:
```
> py C1w1.exec_container("c1", "wget 10.0.0.8:1028")
```
You can run this command from any of the containers in C1.

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

### Check if Skupper is running

```
> ps aux | grep "skupper"
```
should show a skupper process per cluster.

You can also check the config files `/tmp/knetsim/skupper/*.json` here and the log files in the same folder.

## Known Issues

### Pinging containers from workers shuts down Flannel

After the first ping from the worker, the Flannel daemon just stops running breaking everything. Not sure why this is the case. Anyhow, it is recommended to only run interactions from within containers.
