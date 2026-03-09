---
name: compile-macos
description: Compile MindSpore from source on macOS Apple Silicon. Use this skill when the user wants to "compile MindSpore", "build MindSpore from source", "编译MindSpore", "源码编译", mentions "MindSpore compilation on macOS", or discusses building MindSpore on Apple Silicon. Trigger on phrases like "compile mindspore", "build from source", "源码编译mindspore".
version: 1.0.0
---

# MindSpore macOS Compilation

Automated compilation of MindSpore from source for macOS Apple Silicon platform.

## When to Use This Skill

Use this skill when the user wants to:
- Compile MindSpore from source code
- Build MindSpore on macOS Apple Silicon
- Troubleshoot MindSpore compilation issues

## Prerequisites

- **OS**: macOS (Apple Silicon)
- **Compiler**: Apple Clang
- **Python**: 3.10
- **Disk Space**: At least 20GB

## Compilation Steps

### Step 1: Activate Conda Environment

```bash
# Check conda installation
conda --version

# Activate or create environment
conda activate mindspore_py310
# If not exists
conda create -n mindspore_py310 python=3.10 -y
conda activate mindspore_py310
```

### Step 2: Prepare Source Code

**Logic**:
1. Check if already in MindSpore source directory → Success
2. Check if `./mindspore` exists in current directory → `cd mindspore` → Success
3. Otherwise → Clone to current directory → `cd mindspore`

```bash
# Check if in MindSpore source directory (check for build.sh)
if [ -f "build.sh" ]; then
    echo "Already in MindSpore source directory"
elif [ -d "mindspore" ] && [ -f "mindspore/build.sh" ]; then
    echo "Found MindSpore in ./mindspore"
    cd mindspore
else
    echo "Cloning MindSpore source code..."
    git clone -b master https://gitcode.com/mindspore/mindspore.git ./mindspore
    cd mindspore
fi

# Ask user whether to update source code
git fetch origin
git checkout master
git pull origin master
```

### Step 3: Check Dependencies

#### System Tools

**Xcode Command Line Tools** (Required)
```bash
xcode-select -p
# If not installed, prompt user to run:
# xcode-select --install
```

**Install build tools**
```bash
conda install cmake=3.22.3 patch autoconf -y
```

#### Python Packages

```bash
pip install wheel==0.46.3 PyYAML==6.0.2 numpy==1.26.4 -i https://repo.huaweicloud.com/repository/pypi/simple/
```

### Step 4: Compile MindSpore

Set environment variables:

```bash
# Use .mslib in current directory for cache
export MSLIBS_CACHE_PATH=$(pwd)/.mslib
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
export LIBRARY_PATH=$CONDA_PREFIX/lib
export LDFLAGS="-Wl,-rpath,/usr/lib -Wl,-rpath,$CONDA_PREFIX/lib"
```

Execute compilation:

```bash
# Ensure in MindSpore source directory
bash build.sh -e cpu -S on -j4
```

**Parameters**:
- `MSLIBS_CACHE_PATH`: Cache path for third-party libraries
- `-e cpu`: CPU-only build
- `-S on`: Enable symbol table
- `-j4`: Use 4 threads

### Step 5: Install MindSpore

```bash
# Uninstall old version if exists
pip uninstall mindspore -y

# Install dependencies and wheel package
conda install scipy -c conda-forge -y
pip install output/mindspore-*.whl -i https://repo.huaweicloud.com/repository/pypi/simple/
```

### Step 6: Verify Installation

```bash
python -c "import mindspore;mindspore.set_device(device_target='CPU');mindspore.run_check()"
python -c "import mindspore;print(mindspore.__version__)"
```

## Important Notes

1. **Compilation Time**: 30-60 minutes for first build
2. **Disk Space**: Requires at least 20GB
3. **Cache**: MSLIBS_CACHE_PATH avoids re-downloading dependencies
4. **Troubleshooting**: When compilation errors occur, refer to `reference/troubleshooting.md` for historical error records and solutions

## User Interaction Guidelines

- Explain each major step before execution
- Ask user whether to update if source directory exists
- Wait for user to install Xcode Command Line Tools if missing
- Display version info and verification results after completion
- **When compilation fails**: First consult `reference/troubleshooting.md` for matching error patterns and solutions before suggesting generic fixes
- Provide error log location and context-specific solutions based on troubleshooting history
