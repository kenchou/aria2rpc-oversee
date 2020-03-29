Aria2 JSONRPC 任务调度器
=======================

Usage:

```bash
./aria2-oversee.py --jsonrpc http://localhost:6800/jsonrpc --token secret
```

Aria2 RPC 服务设置(systemd)
--------------------------

/etc/systemd/system/aria2rpc.service

```
[Unit]
Description=Aria2 File Download Manager
After=network.target

[Service]
User=<此处替换你的用户名!!!Replace-Your-User-Name-Here!!!>
ExecStart=/usr/bin/aria2c --conf-path=/home/ken/.aria2/aria2.conf --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all
Restart=always

[Install]
WantedBy=default.target
```

/etc/systemd/system/aria2rpc-oversee.service

```
[Unit]
Description=Aria2 File Download Manager
After=network.target aria2rpc.service
Wants=aria2rpc.service

[Service]
User=<此处替换你的用户名!!!Replace-Your-User-Name-Here!!!>
ExecStart=/data/workspace/aria2rpc-oversee/aria2-oversee.py
Restart=always

[Install]
WantedBy=default.target
```
