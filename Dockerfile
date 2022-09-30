FROM ubuntu:focal
MAINTAINER Chander Govindarajan

RUN apt-get update
RUN apt install -y python3 mininet bridge-utils
RUN apt install -y python3-pip
RUN pip3 install mininet

RUN apt install -y iputils-ping traceroute nmap iperf3
# for the killall command
RUN apt install -y psmisc

RUN mkdir downloads

RUN apt install -y wget

# Obtain etcd
RUN cd downloads \
    && wget https://github.com/coreos/etcd/releases/download/v3.0.12/etcd-v3.0.12-linux-amd64.tar.gz \
    && tar -zxvf etcd-v3.0.12-linux-amd64.tar.gz

# Obtain flannel daemon
RUN cd downloads \
    && wget https://github.com/coreos/flannel/releases/download/v0.6.2/flanneld-amd64 -O flanneld \
    && chmod 755 flanneld

# Obtain flannel cni plugin
RUN cd downloads \
    && wget https://github.com/flannel-io/cni-plugin/releases/download/v1.1.0/cni-plugin-flannel-linux-amd64-v1.1.0.tgz \
    && tar -zxvf cni-plugin-flannel-linux-amd64-v1.1.0.tgz

# Obtain generic cni plugins
RUN cd downloads \
    && wget https://github.com/containernetworking/plugins/releases/download/v1.1.1/cni-plugins-linux-amd64-v1.1.1.tgz \
    && tar -zxvf cni-plugins-linux-amd64-v1.1.1.tgz

# Install golang
RUN cd downloads \
    && wget https://go.dev/dl/go1.19.1.linux-amd64.tar.gz \
    && tar -C /usr/local -xvf go1.19.1.linux-amd64.tar.gz

ENV PATH $PATH:/usr/local/go/bin

# Obtain cnitool
RUN go install github.com/containernetworking/cni/cnitool@latest \
    && cp ~/go/bin/cnitool /usr/local/bin

RUN apt install -y iproute2 nftables iptables \
    && update-alternatives --set iptables /usr/sbin/iptables-nft

# copy in main binaries
RUN cd downloads \
    && mv etcd-v3.0.12-linux-amd64/etcd /usr/local/bin/ \
    && mv etcd-v3.0.12-linux-amd64/etcdctl /usr/local/bin/ \
    && mv flanneld /usr/local/bin/

# copy in cni plugin binaries
RUN mkdir -p /opt/cni/bin \
    && cd downloads \
    && cp flannel-amd64 /opt/cni/bin/flannel \
    && cp bridge /opt/cni/bin/ \
    && cp host-local /opt/cni/bin/

COPY . /simulator
WORKDIR /simulator

ENTRYPOINT ./main.py