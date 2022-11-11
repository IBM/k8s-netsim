# knetsim

A learning tool focused on Networking aspects of Kubernetes
(and multi-cluster networking using Skupper)

---

## What it is not 

1. :exclamation: a real Kubernetes setup
2. :exclamation: a single-node k8s runner like minikube, kind

## What it is

1. Mininet based simulation
2. Uses as many real components
3. Models reality as close as possible

---

## What is Kubernetes?

TODO

---

## Aside: Kubernetes is a Complex Beast

+ Many (many) layers and pieces
+ Continuously evolving
+ Huge ecosystem: hundreds of competing startups, open-source projects, products

---

## What is the deal with Kubernetes networking?

1. Connect containers running on different workers
2. Load balance multiple replicas as a single service
3. Expose services by name
4. App net features such as: rate limiting, health checks, blue-green testing

Now, do this across multiple clusters :scream:

---

## Aside: Reality of multi-cluster deployments

Most organization workloads are spanning multiple clusters now.
This is still an unsolved problem!

---

# Rest of the deck is organized as follows

1. Introduce a Kubernetes networking concept
2. Discuss how it works in reality
3. Discuss how we run it in *knetsim*
4. Hands on!

---

# Structure

1. Workers and containers :arrow_left:
2. Container-Container communication
3. Service abstraction
4. Multi-cluster communication

---

# C1: Workers and containers

Kubernetes clusters consist of workers, each running containers

![](https://d33wubrfki0l68.cloudfront.net/2475489eaf20163ec0f54ddc1d92aa8d4c87c96b/e7c81/images/docs/components-of-kubernetes.svg)

---

# C1: How does it work?

1. Each worker is setup with a `kubelet` component that manages containers
2. Containers are run using a runtime, like `containerd` or `docker`

![bg right:60% contain](https://www.suse.com/c/wp-content/uploads/2019/06/cncf-landscape.png)


---

# C1: How do we do it?

1. We use mininet `hosts` to represent each worker.
2. We run network namespaces to represent each container.

---

# Aside: what are namespaces?

TODO

Note: easy to play with network namespaces using the `ip netns` command.

---

# Aside: mininet

TODO

---

# C1: Hands on

Build the image:
```
sudo docker build -t knetsim -f ./Dockerfile .
```

Run the simulator:
```
docker run -it --privileged --rm knetsim
```

---

## Verify if everything is working

```
*** Creating network
...
<ping commands>
*** Starting CLI:
mininet> 
```

---

## Workers 

![bg right:30% fit](../imgs/schema.png)

+ We have 2 clusters with 3 workers each:
+ `C0w1`, `C0w2` and `C0w3` are workers => mininet hosts

Run commands on workers:
```
mininet> C0w1 ifconfig
```
---

## Exercise :hammer:

1. Ping the workers from each other.

---

## Containers

1. Each worker `w<i>` has a container `c<i>`
2. Exec into containers using this command:

```
mininet> py C0w1.exec_container("c1", "ifconfig")
```

---

## Exercise :hammer:

1. Run a few commands in the container. See that only the network namespace is different from the underlying worker.
2. Create new containers:
```
mininet> py C0w1.create_container("c4")
```
(ignore the error it throws)
3. Delete the new container:
```
mininet> py C0w1.delete_container("c4")
```

---

# Progress so far

1. Workers and containers :heavy_check_mark:
2. Container-Container communication :arrow_left:
3. Service abstraction
4. Multi-cluster communication

---

## C2: Container-container communication

TODO
1. Aside: pods vs containers
2. Show example of pods communicating using real k8s example
3. Talk about needs: interface/ip has to be assigned, packets should be routed from one container to another
4. Talk about communication between 2 containers on the same host
5. Talk about communication between 2 containers on different workers: how does flannel, calico, ovn etc do it.
6. Talk about what is common to these: CNI interface
7. Details of CNI interface

---

## C2: How does it work?

TODO

---

## C2: How do we do it?

TODO
We run a real CNI plugin - flannel.
Talk about details of how flannel works

---

## C2: Hands on :hammer:

1. Examine IPs of w1c1 and w2c2.
2. Ping w2c2 from w1c1. Note: use the `ping <ip> -c 5` command.
3. (Optional) Create a new container on one of the workers and see the IP assigned to it and check if you can connect to it.

---

## C2: Hands on

TODO
1. Add diagram of the traffic flow from c1 to c2.
2. Examine these hook points using some commands.

---

## C2: Optional Exercises

1. Examine the logs of flannel in the `/tmp/knetsim` folder.
2. Change the parameters of the flannel config in `conf` folder and re-run and see the change in IPs.

---

# Progress so far

1. Workers and containers :heavy_check_mark:
2. Container-Container communication :heavy_check_mark:
3. Service abstraction :arrow_left:
4. Multi-cluster communication

---

## C3: Service Abstraction
