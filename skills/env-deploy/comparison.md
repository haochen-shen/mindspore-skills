# Comparison: env-deploy-old vs env-deploy (new)

## Key Differences

### What env-deploy-old has that new skill lacks:

1. **Package Manager Choice (uv vs conda)**
   - Old skill asks about uv (faster) vs conda
   - New skill only mentions conda

2. **Network Troubleshooting**
   - Proxy configuration for uv/conda/pip
   - Mirror sites (Tsinghua, Aliyun for China)
   - Timeout settings
   - DNS resolution issues

3. **Detailed CANN Installation**
   - Specific package names (Ascend-cann-toolkit, Ascend-cann-kernels)
   - Installation commands with --install-path
   - Environment variable setup (set_env.sh)
   - Shell profile persistence
   - npu-smi verification

4. **Troubleshooting Section**
   - Import errors with solutions
   - CANN not found diagnostics
   - NPU device detection issues
   - Version mismatch handling
   - Permission issues (HwHiAiUser group)

5. **Environment Variables Reference**
   - Complete list of CANN environment variables
   - ASCEND_TOOLKIT_HOME, LD_LIBRARY_PATH, etc.

6. **Advanced Verification**
   - Beyond run_check: actual tensor operations
   - Device context verification
   - NPU allocation testing

7. **Common Issues Tables**
   - Network issues with solutions
   - CANN installation issues
   - MindSpore installation issues

8. **Version Compatibility Matrix**
   - MindSpore <-> CANN version mapping
   - Python version support

9. **Troubleshooting Red Flags**
   - "User wants quick fix" rationalization
   - "Just network issues" rationalization
   - Emphasis on gathering context first

### What new skill has that old skill lacks:

1. **Structured Decision Workflow**
   - Flowchart showing decision points
   - Clear branching for CPU/GPU/Ascend

2. **Pressure Resistance Section**
   - Red flags for time pressure
   - Rationalization table

3. **Example Dialogue**
   - Shows complete interaction flow

4. **Source Compilation Option**
   - References compile-macos skill

5. **TDD-tested**
   - Baseline scenarios documented
   - Verified compliance

## Recommendations for Upgrading New Skill

### High Priority (Must Add):
1. Add uv as package manager option
2. Add detailed CANN installation steps
3. Add network troubleshooting section
4. Add environment variables reference
5. Add troubleshooting section with common issues
6. Add version compatibility guidance

### Medium Priority (Should Add):
7. Add advanced verification beyond run_check
8. Add permission issues (HwHiAiUser group)
9. Add npu-smi verification command

### Low Priority (Nice to Have):
10. Add version compatibility matrix
11. Add useful commands reference
12. Add next steps section

## Integration Strategy

Merge the strengths:
- Keep new skill's structured workflow and pressure resistance
- Add old skill's detailed technical content
- Combine troubleshooting approaches
- Maintain TDD-tested discipline enforcement
