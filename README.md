# knetsim

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
