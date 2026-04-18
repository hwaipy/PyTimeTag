# Hosts Updater

自动从 [ineo6/hosts](https://gitlab.com/ineo6/hosts) 获取 GitHub hosts 并更新本机 `/etc/hosts`。

## 功能

- 每 6 小时自动拉取最新 GitHub hosts
- 保留原有的本地 hosts 条目
- 在 `/etc/hosts.history.txt` 记录每次更新历史
- 开机后 1 分钟内自动启动，无感运行

## 安装

```bash
cd hosts-updater
sudo python3 hosts_updater.py install
```

安装后会创建两个 systemd 单元：
- `hosts-updater.service` — 执行更新的 oneshot 服务
- `hosts-updater.timer` — 每 6 小时触发一次的定时器

## 使用

```bash
# 立即执行一次更新
sudo python3 hosts_updater.py run

# 查看状态和历史记录
python3 hosts_updater.py status

# 查看定时器状态
systemctl status hosts-updater.timer

# 查看日志
journalctl -u hosts-updater.service -f
```

## 卸载

```bash
sudo systemctl stop hosts-updater.timer
sudo systemctl disable hosts-updater.timer
sudo rm /etc/systemd/system/hosts-updater.service
sudo rm /etc/systemd/system/hosts-updater.timer
sudo systemctl daemon-reload
```
