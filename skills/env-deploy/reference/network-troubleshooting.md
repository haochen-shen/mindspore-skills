# Network Troubleshooting

## Proxy Configuration

### For Conda

```bash
conda config --set proxy_servers.http http://proxy.example.com:8080
conda config --set proxy_servers.https http://proxy.example.com:8080
```

### For Pip

```bash
pip config set global.proxy http://proxy.example.com:8080

# Or use environment variables
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## Mirror Sites (China Users)

### Conda Mirrors

```bash
# Tsinghua mirror
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --set show_channel_urls yes

# Aliyun mirror
conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/free/
conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/main/
```

### Pip Mirrors

```bash
# Tsinghua mirror
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Aliyun mirror
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# Or use -i flag for one-time use
pip install mindspore -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## Common Network Issues

| Issue | Solution |
|-------|----------|
| Slow download | Use mirror sites or download manager |
| Connection timeout | Configure proxy, increase timeout with `--timeout 300` |
| SSL certificate error | Use `--trusted-host` for pip: `pip install --trusted-host pypi.org mindspore` |
| DNS resolution failure | Check `/etc/resolv.conf`, use public DNS (8.8.8.8, 1.1.1.1) |
| Firewall blocking | Check corporate firewall rules, whitelist required domains |

## Timeout Settings

```bash
# Increase pip timeout
pip install mindspore --timeout 300

# Increase conda timeout
conda config --set remote_read_timeout_secs 300
```

## Testing Network Connectivity

```bash
# Test conda connectivity
conda info

# Test pip connectivity
pip search mindspore

# Test direct URL access
curl -I https://pypi.org/simple/mindspore/
```

## Corporate Network Issues

If behind corporate firewall:

1. **Get proxy settings from IT department**
2. **Configure proxy for all tools** (conda, pip, wget, curl)
3. **Add SSL certificates** if using corporate SSL inspection
4. **Whitelist required domains:**
   - pypi.org
   - repo.anaconda.com
   - www.mindspore.cn
   - www.hiascend.com

## Offline Installation

If network is completely unavailable:

1. **Download packages on a machine with internet**
2. **Transfer to target machine**
3. **Install from local files:**

```bash
# Install conda from local file
bash Miniconda3-latest-Linux-x86_64.sh

# Install pip packages from local wheels
pip install mindspore-*.whl --no-index --find-links ./wheels/
```
