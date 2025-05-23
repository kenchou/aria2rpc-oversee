Aria2 JSONRPC 任务调度器
=======================

  This is a download task scheduler designed for `Aria2` RPC mode. It periodically checks the download progress every few minutes. If a task remains stalled for an extended period, it will be moved to the end of the waiting queue to prevent blockages, thereby optimizing overall system resources to prioritize faster completion of downloads.

  这是一个为 `Aria2` RPC 模式设计的下载任务调度程序。它每个几分钟查询下载进度。如果某个任务长时间没有进展，会被调到等待队列的末尾，不要阻塞等待队列。这样总体上可以让更多的资源尽快下载完成。

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
