#!/usr/bin/env bash

mkdir downloads
cd downloads

wget https://github.com/coreos/etcd/releases/download/v3.0.12/etcd-v3.0.12-linux-amd64.tar.gz
tar zxvf etcd-v3.0.12-linux-amd64.tar.gz

wget https://github.com/coreos/flannel/releases/download/v0.6.2/flanneld-amd64 -O flanneld && chmod 755 flanneld
