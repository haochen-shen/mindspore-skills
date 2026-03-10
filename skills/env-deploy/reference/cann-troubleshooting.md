# CANN Installation and Troubleshooting

## Installation Steps

### 1. Download CANN Packages

Visit: https://www.hiascend.com/software/cann/community

Select based on:
- Operating system (Linux x86_64, Linux aarch64)
- CANN version (recommend latest stable, e.g., 8.0.RC3)
- Python version (must match your environment)

### 2. Required CANN Packages

1. `Ascend-cann-toolkit` - Core toolkit
2. `Ascend-cann-kernels-{arch}` - Kernel libraries
   - 910 for training (Ascend 910)
   - 310 for inference (Ascend 310)

### 3. Installation Commands

```bash
# Extract packages
tar -xzf Ascend-cann-toolkit_*.tar.gz
tar -xzf Ascend-cann-kernels-*.tar.gz

# Install toolkit
cd Ascend-cann-toolkit
./install.sh --install-path=/usr/local/Ascend

# Install kernels
cd ../Ascend-cann-kernels-*
./install.sh --install-path=/usr/local/Ascend

# Set environment variables
source /usr/local/Ascend/ascend-toolkit/set_env.sh
```

### 4. Make Environment Variables Persistent

```bash
# For bash
echo "source /usr/local/Ascend/ascend-toolkit/set_env.sh" >> ~/.bashrc

# For zsh
echo "source /usr/local/Ascend/ascend-toolkit/set_env.sh" >> ~/.zshrc

# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc
```

### 5. Verify CANN Installation

```bash
# Check NPU device status
npu-smi info

# Check CANN version
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
```

## Version Compatibility

| MindSpore Version | CANN Version | Python Version |
|-------------------|--------------|----------------|
| 2.3.x | 8.0.RC3 | 3.9-3.12 |
| 2.2.x | 7.0.x | 3.8-3.11 |
| 2.1.x | 6.3.x | 3.7-3.10 |

Check official compatibility: https://www.mindspore.cn/install

## Common CANN Issues

### Permission Denied

**Problem:** Cannot install CANN due to permission errors

**Solution:**
```bash
# Use sudo for installation
sudo ./install.sh --install-path=/usr/local/Ascend

# Or install to user directory
./install.sh --install-path=$HOME/Ascend
```

### Library Not Found

**Problem:** `libascendcl.so` or other CANN libraries not found

**Solution:**
```bash
# Verify environment variables
echo $ASCEND_TOOLKIT_HOME
echo $LD_LIBRARY_PATH

# Re-source CANN environment
source /usr/local/Ascend/ascend-toolkit/set_env.sh

# Check if libraries exist
ls /usr/local/Ascend/ascend-toolkit/latest/lib64/
```

### Version Conflict

**Problem:** Multiple CANN versions installed causing conflicts

**Solution:**
```bash
# Uninstall old CANN
sudo rm -rf /usr/local/Ascend

# Clean environment variables
unset ASCEND_TOOLKIT_HOME
unset LD_LIBRARY_PATH

# Reinstall correct version
./install.sh --install-path=/usr/local/Ascend
```

### Driver Mismatch

**Problem:** CANN version doesn't match Ascend driver

**Solution:**
```bash
# Check driver version
cat /usr/local/Ascend/driver/version.info

# Update driver to match CANN version
# Download matching driver from https://www.hiascend.com/hardware/firmware-drivers
sudo ./Ascend-hdk-*.run --full
```

### NPU Device Not Detected

**Problem:** `npu-smi info` shows no devices

**Solution:**
```bash
# Check if driver is loaded
lsmod | grep drv_davinci

# Restart NPU service
sudo systemctl restart ascend-hccl.service

# Check device files
ls /dev/davinci*

# Check dmesg for errors
dmesg | grep -i ascend
```

### Permission Issues (HwHiAiUser Group)

**Problem:** Permission denied when accessing NPU devices

**Solution:**
```bash
# Add user to HwHiAiUser group
sudo usermod -a -G HwHiAiUser $USER

# Verify group membership
groups $USER

# Re-login or use newgrp
newgrp HwHiAiUser

# Check device permissions
ls -l /dev/davinci*
```

## Environment Variables Reference

### Required Environment Variables

```bash
# CANN toolkit path
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest
export LD_LIBRARY_PATH=${ASCEND_TOOLKIT_HOME}/lib64:$LD_LIBRARY_PATH
export PATH=${ASCEND_TOOLKIT_HOME}/bin:$PATH
export PYTHONPATH=${ASCEND_TOOLKIT_HOME}/python/site-packages:$PYTHONPATH

# CANN OPP path (operator packages)
export ASCEND_OPP_PATH=${ASCEND_TOOLKIT_HOME}/opp

# CANN AICPU path
export ASCEND_AICPU_PATH=${ASCEND_TOOLKIT_HOME}/
```

### Optional Debug Variables

```bash
# Enable debug logging
export GLOG_v=1
export ASCEND_SLOG_PRINT_TO_STDOUT=1

# Set log level
export ASCEND_GLOBAL_LOG_LEVEL=1  # 0=debug, 1=info, 2=warning, 3=error

# Enable profiling
export PROFILING_MODE=true
export PROFILING_OPTIONS=training_trace
```

## Verification Commands

```bash
# Check CANN installation
ls /usr/local/Ascend/ascend-toolkit/latest/

# Check NPU devices
npu-smi info

# Check driver version
cat /usr/local/Ascend/driver/version.info

# Check environment variables
env | grep ASCEND

# Test CANN functionality
python -c "import acl; print('CANN is working')"
```

## Uninstallation

If you need to completely remove CANN:

```bash
# Stop services
sudo systemctl stop ascend-hccl.service

# Remove CANN installation
sudo rm -rf /usr/local/Ascend

# Remove environment variables from shell profile
# Edit ~/.bashrc or ~/.zshrc and remove CANN-related lines

# Reload shell
source ~/.bashrc
```
