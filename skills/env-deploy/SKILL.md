---
name: env-deploy
description: Use when user requests MindSpore environment setup, installation, or deployment; mentions creating conda/venv environments for MindSpore; asks about installing MindSpore packages; or encounters MindSpore installation failures
---

# MindSpore Environment Deployment

## Overview

Structured workflow for deploying MindSpore environments. Enforces critical decision points to prevent installation failures.

**Core principle:** No assumptions. Every critical choice requires explicit user decision.

## When to Use

Use when:
- User requests MindSpore installation or setup
- User mentions creating development environment for MindSpore
- User encounters MindSpore installation failures
- User asks about MindSpore deployment

Do NOT use for:
- MindSpore code debugging (use systematic-debugging)
- Operator development (use mscode:*-builder skills)
- Model migration (use mscode:*-migrate skills)

## Critical Decision Points

### 1. Operating System (ALWAYS ASK)

**Never assume operating system.** Ask explicitly:

```
"Which operating system are you using?
1. Linux - requires conda for environment management
2. Windows - uses pip directly (no conda needed)
3. macOS ARM64 (Apple Silicon) - requires conda"
```

**Why:** Different OS have different installation requirements. Windows can use pip directly, while Linux/macOS need conda.

**Supported Platforms (Official):**
- Linux x86_64, Linux aarch64
- Windows x86_64
- macOS ARM64 (Apple Silicon)

### 2. Conda Availability (CHECK FOR LINUX/MACOS)

**For Linux and macOS only, check if conda is installed:**

```bash
which conda
```

**If conda is not available, guide user to install Miniconda:**

```bash
# Linux x86_64
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate
conda init

# Linux aarch64
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate
conda init

# macOS ARM64 (Apple Silicon)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate
conda init
```

**After installation, restart shell or source profile:**

```bash
source ~/.bashrc  # or ~/.zshrc for zsh
```

**Why:** Conda is required for environment management on Linux/macOS. Windows users can use venv or pip directly.

### 3. Python Version (ALWAYS ASK)

**Never assume Python version.** Ask explicitly:

```
"Which Python version would you like to use? (Supported: 3.7-3.12, Recommended: 3.9-3.12)"
```

**Official Support:** Python >=3.7 (3.7, 3.8, 3.9, 3.10, 3.11, 3.12)

**Why:** MindSpore compatibility varies by version. User may have specific requirements.

### 4. Device Type (ALWAYS ASK)

**Never assume device type.** Present options and require choice:

```
"Which device type will you use?
1. CPU - for development and testing (all platforms)
2. Ascend - requires CANN toolkit (Linux only, Huawei NPU)"
```

**Official Hardware Support:**
- **Ascend**: Linux x86_64, Linux aarch64
- **CPU**: Linux x86_64, Linux aarch64, Windows x86_64, macOS ARM64

**Why:** Wrong device type = wasted installation time and potential incompatibility.

### 5. Installation Method (ALWAYS ASK)

**Never assume installation method.** Ask explicitly:

```
"How would you like to install MindSpore?
1. Prebuilt wheel from official PyPI (faster, recommended)
2. Compile from source (slower, for custom builds or unsupported platforms)"
```

**Why:** Source compilation is complex and time-consuming. Only use when necessary. Most users should use prebuilt wheels.

### 6. CANN Installation (REQUIRED FOR ASCEND)

**If device type is Ascend, ALWAYS check CANN:**

```bash
# Check if CANN is installed
ls /usr/local/Ascend/ascend-toolkit/latest/

# If not found, guide user to install CANN first
```

**Why:** MindSpore Ascend requires CANN toolkit. Installation will fail without it.

## Implementation Steps

### Step 1: Create Environment

**For Linux and macOS:**

Check if conda is installed:
```bash
which conda
```

If conda is not found, install Miniconda (see Critical Decision Points section 2).

Create conda environment:
```bash
# After getting Python version from user
conda create -n mindspore_env python=3.9 -y
conda activate mindspore_env
```

**For Windows:**

Use Python's built-in venv:
```cmd
# Create virtual environment
python -m venv mindspore_env

# Activate environment
mindspore_env\Scripts\activate
```

### Step 2: Install MindSpore

**Option A: Prebuilt Wheel (Recommended)**

Official installation command:

```bash
pip install mindspore==2.7.1 -i https://repo.mindspore.cn/pypi/simple --trusted-host repo.mindspore.cn
```

Alternative (PyPI):

```bash
pip install mindspore
```

**Platform-specific notes:**
- **CPU**: Supported on all platforms (Linux, Windows, macOS ARM64)
- **Ascend**: Linux only, requires CANN (see Step 3)

**Option B: Compile from Source**

For custom builds or unsupported platforms, use the compile-macos skill:

```
**REQUIRED:** Use mscode:compile-macos skill for source compilation
```

### Step 3: CANN Installation (Ascend Only)

If user selected Ascend and CANN is not installed, see `cann-troubleshooting.md` for complete installation guide.

### Step 4: Verification (ALWAYS REQUIRED)

**Never skip verification.** Always use run_check:

```bash
# Official MindSpore verification command
python -c "import mindspore;mindspore.set_device(device_target='CPU');mindspore.run_check()"

# For Ascend
python -c "import mindspore;mindspore.set_device(device_target='Ascend');mindspore.run_check()"
```

**Why:** Simple import test is insufficient. run_check verifies:
- Installation completeness
- Device availability
- Backend functionality
- Version compatibility

**Expected output:**
```
MindSpore version: 2.x.x
The result of multiplication calculation is correct, MindSpore has been installed on platform [CPU/Ascend] successfully!
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Assuming OS | Always ask explicitly |
| Assuming conda on Windows | Windows uses venv |
| Using `import mindspore` for verification | Use `mindspore.run_check()` with device target |
| Skipping CANN check for Ascend | Always verify CANN first |
| Not using official PyPI mirror | Use `-i https://repo.mindspore.cn/pypi/simple` |

## Pressure Resistance

### Red Flags - STOP and Ask Questions

- "Quickly set up..."
- "Just give me commands..."
- "I know what I'm doing..."
- "Senior engineer recommended..."
- "Just make it work..."
- "Same setup as last time..."
- "Skip verification..."

**All of these mean: Ask critical questions anyway. No exceptions.**

### Key Rationalizations to Reject

| Rationalization | Reality |
|----------------|---------|
| "Quick means skip questions" | Questions take 30 seconds. Wrong install wastes hours. |
| "User sounds confident" | Confidence ≠ complete information. Ask anyway. |
| "Working import = success" | Import test insufficient. Use run_check. |
| "Same setup as last time" | Requirements may have changed. Verify current needs. |
| "User will test themselves" | run_check is non-negotiable. Always verify. |

For complete list, see `reference/pressure-resistance.md`

## Troubleshooting

For detailed troubleshooting, see reference directory:

- **Network issues** → `reference/network-troubleshooting.md`
- **CANN issues** → `reference/cann-troubleshooting.md`
- **MindSpore issues** → `reference/mindspore-troubleshooting.md`

## Real-World Impact

**Without this workflow:**
- Users install wrong device type
- Installations fail due to missing CANN
- Verification skipped, issues discovered later

**With this workflow:**
- All critical decisions made upfront
- Installation succeeds first time
- Proper verification confirms functionality
