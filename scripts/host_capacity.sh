#!/usr/bin/env bash
# host_capacity.sh — 采集与评测容量相关的硬件/系统快照(全部只读,不改任何状态)。
# 用途: 把整份输出粘贴给分析,估算这台机器能同时跑多少路靶场(agent 容器 + 靶机容器)。
# 用法: bash scripts/host_capacity.sh   (在评测服务器上执行)

set -u

hr() { printf '\n===== %s =====\n' "$*"; }

hr "CPU / 负载"
lscpu 2>/dev/null | grep -E '^(Model name|Socket\(s\)|Core\(s\) per socket|Thread\(s\) per core|CPU\(s\):)' || \
  grep -c processor /proc/cpuinfo | sed 's/^/processors: /'
echo "loadavg:   $(cat /proc/loadavg)"
echo "uptime:    $(uptime -p 2>/dev/null)"

hr "内存"
free -h
echo "swap:"
swapon --show 2>/dev/null | sed 's/^/  /' || echo "  (none)"
grep -E '^Huge(Total|Free)' /proc/meminfo | sed 's/^/  /'

hr "磁盘"
df -h / /var/lib/docker 2>/dev/null | awk '!seen[$1]++' | sed 's/^/  /'
lsblk -d -o NAME,SIZE,ROTA,MODEL 2>/dev/null | sed 's/^/  /'
docker system df 2>/dev/null | sed 's/^/  /'

hr "内核 / ASLR"
uname -r
echo "randomize_va_space = $(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)  (0=off,2=full; 评测 profile 期望 0)"

hr "fd / conntrack / 端口"
echo "nofile ulimit (soft/hard): $(ulimit -Sn) / $(ulimit -Hn)"
echo "conntrack: $(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || echo n/a) / $(cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo n/a)"
echo "ip_local_port_range: $(cat /proc/sys/net/ipv4/ip_local_port_range 2>/dev/null)"

hr "Docker"
docker version --format 'server {{.Server.Version}}' 2>/dev/null | sed 's/^/  /'
docker info 2>/dev/null | grep -E 'Containers:| *Running:| *Paused:| *Stopped:|Images:|Docker Root Dir|Total Memory|NCPU' | sed 's/^/  /'
echo "networks: $(docker network ls -q 2>/dev/null | wc -l) 个"
[ -r /etc/docker/daemon.json ] && { echo "daemon.json:"; sed 's/^/  /' /etc/docker/daemon.json; }
echo "running containers: $(docker ps -q 2>/dev/null | wc -l)"
echo "all containers:     $(docker ps -aq 2>/dev/null | wc -l)"

hr "在跑容器按归属(exploitgym.owner label)"
docker ps --format '{{.Label "exploitgym.owner"}}|{{.Names}}' 2>/dev/null | awk -F'|' '{o=$1; if(o=="") o="<无label>"; c[o]++} END {for (k in c) printf "  %-16s %d\n", k, c[k]}'

hr "容器内存占用 TOP10"
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null \
  | sort -t"$(printf '\t')" -k2 -hr | head -10 | column -t -s"$(printf '\t')" 2>/dev/null \
  || docker stats --no-stream 2>/dev/null | head -12

hr "容器内存合计 / QEMU 进程数"
docker stats --no-stream --format '{{.MemUsage}}' 2>/dev/null | cut -d'/' -f1 | python3 -c "
import sys
tot = 0.0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    mul = 1
    for suf, m in (('TiB', 2**40), ('GiB', 2**30), ('MiB', 2**20), ('KiB', 2**10), ('B', 1)):
        if line.endswith(suf):
            try:
                tot += float(line[: -len(suf)].strip()) * m
            except ValueError:
                pass
            break
print(f'  合计: {tot / 2**30:.1f} GiB')
" 2>/dev/null
echo "qemu 进程: $(pgrep -c -f 'qemu-system' 2>/dev/null || echo 0)"

hr "宿主机 RSS TOP6"
ps -eo rss,comm --sort=-rss --no-headers 2>/dev/null | head -6 | \
  awk '{printf "  %7.2f GiB  %s\n", $1/1048576, $2}'

hr "容量初估(按 user 任务每路 ~3GiB 计)"
python3 - <<'EOF'
import os

with open('/proc/meminfo') as f:
    mi = {l.split(':')[0]: int(l.split()[1]) for l in f if ':' in l}
total_g = mi['MemTotal'] / 2**20
avail_g = mi['MemAvailable'] / 2**20
ncpu = os.cpu_count() or 1

usable = total_g * 0.75          # 预留 25% 给宿主机/页缓存
lanes_mem = int(usable / 3)      # user 任务每路 ~3GiB(agent 容器 + 靶机)
lanes_kernel = int(usable / 5.5) # kernel 任务每路多一个 ~2.5GiB 的 QEMU
lanes_cpu = int(ncpu * 1.5)      # cc 以网络等待为主,CPU 可适度超卖

print(f"  内存: total={total_g:.0f}G avail={avail_g:.0f}G")
print(f"  CPU:  {ncpu} 核, load 建议上限 ~{ncpu}")
print(f"  → user 任务建议 MAX_WORKERS ≤ {max(1, min(lanes_mem, lanes_cpu))} (内存上限 {lanes_mem}, CPU 上限 {lanes_cpu})")
print(f"  → kernel 任务建议 ≤ {max(1, min(lanes_kernel, lanes_cpu))} (QEMU 每路多占 ~2.5G)")
print("  (粗估: 2h 超时预算可容忍一定超卖; 上线后用 free/uptime/docker stats 复核)")
EOF

printf '\n===== done =====\n'
