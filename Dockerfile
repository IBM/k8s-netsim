FROM ubuntu:jammy
MAINTAINER Chander Govindarajan

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt install -y python3 mininet bridge-utils python3-pip wget
RUN pip3 install mininet

RUN apt install -y iputils-ping traceroute nmap iperf3 psmisc iproute2 nftables iptables \
    && update-alternatives --set iptables /usr/sbin/iptables-nft

RUN mkdir downloads

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

## Skupper Router related things
# Obtain skupper source code
RUN cd downloads \
    && wget https://github.com/skupperproject/skupper-router/archive/refs/tags/2.1.0.tar.gz \
    && tar -xzvf 2.1.0.tar.gz

# Obtain skupper build dependencies
RUN apt install -y cmake \
    libqpid-proton11 libqpid-proton11-dev python3-qpid-proton \
    libnghttp2-dev libwebsockets-dev \
    asciidoc

# Obtain qpid-proton src - needed to build skupper router
RUN cd downloads \
    && wget https://github.com/apache/qpid-proton/archive/main.tar.gz -O qpid-proton.tar.gz \
    && tar -zxf qpid-proton.tar.gz --one-top-level=qpid-proton-src --strip-components 1

# Build dependency needed for qpid-proton
RUN apt install -y libssl-dev

# Build qpid-proton library
RUN cd downloads \
    && cmake -S "qpid-proton-src" -B "proton_build" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DRUNTIME_CHECK="${runtime_check}" \
    -DENABLE_LINKTIME_OPTIMIZATION=ON \
    -DCMAKE_POLICY_DEFAULT_CMP0069=NEW -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON \
    -DBUILD_TLS=ON -DSSL_IMPL=openssl -DBUILD_STATIC_LIBS=ON -DBUILD_BINDINGS=python -DSYSINSTALL_PYTHON=ON \
    -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF \
    -DCMAKE_INSTALL_PREFIX=/usr \
    && cmake --build "proton_build" --parallel 4 --verbose \
    && DESTDIR="proton_install" cmake --install "proton_build"

# Build skupper itself
RUN cd downloads/skupper-router-2.1.0/ \
    && cmake -S . -B ../skupper-router-build \
       -DProton_USE_STATIC_LIBS=ON \
       -DProton_DIR="../proton_install/usr/lib/cmake/Proton" \
       -DCMAKE_INSTALL_PREFIX=/usr \
       -DBUILD_TESTING=OFF \
       -DVERSION=2.1.0 \
    && cmake --build ../skupper-router-build --parallel 4 \
    && cmake --install ../skupper-router-build

# generate skupper docs
RUN cd downloads/skupper-router-build \
    && make docs
# Now doc files are available in the folder /downloads/skupper-router-build/docs/man
# Of interest is the adoc files

# Needed to run skupper router
ENV PYTHONPATH=/usr/lib/python3.10/site-packages/

RUN apt-get install -y tcpdump
RUN apt-get install -y tshark
RUN apt-get install -y less

RUN apt-get update
RUN apt-get install -y curl

COPY . /simulator
WORKDIR /simulator

ENTRYPOINT ./main.py