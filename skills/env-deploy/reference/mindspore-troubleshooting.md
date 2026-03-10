# MindSpore Installation Troubleshooting

## If run_check Fails

### 1. Import Error

**Problem:** Cannot import mindspore module

**Diagnostics:**
```bash
# Check Python path
which python
python -c "import sys; print(sys.path)"

# Check if mindspore is installed
pip list | grep mindspore

# Check installation location
pip show mindspore
```

**Solution:**
```bash
# Reinstall MindSpore
pip uninstall mindspore
pip install mindspore-*.whl

# Or reinstall from PyPI
pip install mindspore --force-reinstall
```

### 2. CANN Not Found

**Problem:** MindSpore cannot find CANN libraries

**Diagnostics:**
```bash
# Verify CANN environment variables
echo $ASCEND_TOOLKIT_HOME
echo $LD_LIBRARY_PATH

# Check if CANN libraries exist
ls /usr/local/Ascend/ascend-toolkit/latest/lib64/
```

**Solution:**
```bash
# Re-source CANN environment
source /usr/local/Ascend/ascend-toolkit/set_env.sh

# Add to current session
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest
export LD_LIBRARY_PATH=${ASCEND_TOOLKIT_HOME}/lib64:$LD_LIBRARY_PATH

# Verify MindSpore can find CANN
python -c "import mindspore; print(mindspore.__version__)"
```

### 3. NPU Device Not Detected

**Problem:** MindSpore cannot detect NPU devices

**Diagnostics:**
```bash
# Check NPU status
npu-smi info

# Check driver
cat /usr/local/Ascend/driver/version.info

# Check device files
ls -l /dev/davinci*

# Check dmesg for errors
dmesg | grep -i ascend
```

**Solution:**
```bash
# Restart NPU service (requires root)
sudo systemctl restart ascend-hccl.service

# Check if driver is loaded
lsmod | grep drv_davinci

# If driver not loaded, reload it
sudo modprobe drv_davinci
```

### 4. Version Mismatch

**Problem:** MindSpore version incompatible with CANN version

**Diagnostics:**
```bash
# Check MindSpore version
python -c "import mindspore; print(mindspore.__version__)"

# Check CANN version
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
```

**Solution:**
- Ensure CANN version matches MindSpore requirements
- Check compatibility matrix: https://www.mindspore.cn/install
- Reinstall matching versions

**Version Compatibility:**
| MindSpore | CANN | Python |
|-----------|------|--------|
| 2.3.x | 8.0.RC3 | 3.9-3.12 |
| 2.2.x | 7.0.x | 3.8-3.11 |
| 2.1.x | 6.3.x | 3.7-3.10 |

### 5. Permission Issues

**Problem:** Permission denied when accessing NPU devices

**Diagnostics:**
```bash
# Check current user groups
groups $USER

# Check device permissions
ls -l /dev/davinci*
```

**Solution:**
```bash
# Add user to HwHiAiUser group
sudo usermod -a -G HwHiAiUser $USER

# Verify group membership
groups $USER

# Re-login or use newgrp
newgrp HwHiAiUser

# Test access
npu-smi info
```

## Common MindSpore Issues

### Wheel Not Compatible

**Problem:** Downloaded wheel is not compatible with system

**Solution:**
- Check Python version matches wheel requirements
- Check platform (Linux x86_64, aarch64, etc.)
- Check CANN version matches wheel requirements
- Download correct wheel from https://www.mindspore.cn/install

### Dependency Conflict

**Problem:** Conflicting package dependencies

**Solution:**
```bash
# Create fresh conda environment
conda deactivate
conda env remove -n mindspore_env
conda create -n mindspore_env python=3.9 -y
conda activate mindspore_env

# Install MindSpore in clean environment
pip install mindspore
```

### Import Error After Installation

**Problem:** MindSpore imports but fails at runtime

**Diagnostics:**
```bash
# Check LD_LIBRARY_PATH includes CANN
echo $LD_LIBRARY_PATH | grep Ascend

# Check Python can find CANN libraries
python -c "import ctypes; ctypes.CDLL('/usr/local/Ascend/ascend-toolkit/latest/lib64/libascendcl.so')"
```

**Solution:**
```bash
# Ensure CANN environment is sourced
source /usr/local/Ascend/ascend-toolkit/set_env.sh

# Verify LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/usr/local/Ascend/ascend-toolkit/latest/lib64:$LD_LIBRARY_PATH

# Test import
python -c "import mindspore; mindspore.run_check()"
```

### Segmentation Fault

**Problem:** Python crashes with segmentation fault

**Possible Causes:**
1. CANN installation corrupted
2. Driver version mismatch
3. Incompatible library versions
4. Memory issues

**Solution:**
```bash
# Check CANN installation integrity
ls /usr/local/Ascend/ascend-toolkit/latest/lib64/ | wc -l

# Reinstall CANN if needed
sudo rm -rf /usr/local/Ascend
# Then reinstall CANN

# Check driver version matches CANN
cat /usr/local/Ascend/driver/version.info

# Update driver if needed
sudo ./Ascend-hdk-*.run --full
```

## Advanced Verification

Beyond `run_check`, test MindSpore functionality:

```python
import mindspore as ms
from mindspore import Tensor, ops

# Set device target
ms.set_context(device_target="Ascend", device_id=0)

# Test basic operation
x = Tensor([1.0, 2.0, 3.0])
y = Tensor([4.0, 5.0, 6.0])
result = ops.add(x, y)
print(f"Add result: {result}")

# Verify device
print(f"Device: {ms.get_context('device_target')}")
print(f"Device ID: {ms.get_context('device_id')}")

# Test tensor allocation
large_tensor = Tensor(np.random.randn(1000, 1000), ms.float32)
print(f"Large tensor shape: {large_tensor.shape}")
```

## Useful Diagnostic Commands

```bash
# Check versions
python --version
pip list | grep mindspore
npu-smi info

# Environment info
python -m mindspore.run_check
python -c "import mindspore; print(mindspore.get_context('device_target'))"

# Clean reinstall
pip uninstall mindspore
rm -rf ~/.cache/pip
pip install mindspore-*.whl

# Check library dependencies
ldd $(python -c "import mindspore; print(mindspore.__file__)")
```

## Getting Help

If issues persist:

1. **Check official documentation:** https://www.mindspore.cn/install
2. **Search community forum:** https://www.mindspore.cn/community
3. **Check GitHub issues:** https://github.com/mindspore-ai/mindspore/issues
4. **Provide diagnostic info when asking for help:**
   - MindSpore version
   - CANN version
   - Python version
   - Operating system
   - Error messages
   - Output of `npu-smi info`
