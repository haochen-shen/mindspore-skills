# Test Scenarios for env-deploy Skill

## Scenario 1: Time Pressure + Missing Information
**Setup:** Agent asked to "quickly set up MindSpore for testing"
**Pressures:**
- Time urgency ("quickly")
- No device type specified
- No Python version specified
- No installation method specified

**Expected Failures Without Skill:**
- Skips asking critical questions (device type, Python version)
- Assumes defaults without confirmation
- Installs wrong device type (e.g., CPU when user needs Ascend)
- Skips verification step
- Uses incompatible Python version

**Test Command:**
"I need to quickly set up a MindSpore environment for testing. Can you help?"

---

## Scenario 2: Authority Pressure + Sunk Cost
**Setup:** User says "senior engineer recommended CPU version" but actually needs Ascend
**Pressures:**
- Authority bias (senior engineer)
- Sunk cost (if agent already started CPU install)
- Implicit time pressure

**Expected Failures Without Skill:**
- Follows authority without questioning device requirements
- Continues with wrong installation after starting
- Doesn't verify actual hardware/needs
- Skips CANN installation even if Ascend available

**Test Command:**
"Our senior engineer said to use CPU version of MindSpore. Set that up for me."
(Then reveal: "Oh wait, I have Ascend 910B hardware")

---

## Scenario 3: Exhaustion + Complexity
**Setup:** User tried manual installation, failed, now asking for help
**Pressures:**
- User frustration/exhaustion
- Partial existing setup (broken state)
- Multiple failure points
- Urgency to "just make it work"

**Expected Failures Without Skill:**
- Skips cleanup of broken environment
- Doesn't ask about existing installations
- Misses CANN version compatibility
- Skips run_check verification
- Uses source compilation when prebuilt would work

**Test Command:**
"I've been trying to install MindSpore for hours and it keeps failing. Can you just fix it? I have Python 3.9 and some conda env already."

---

## Scenario 4: Overconfidence + Missing Steps
**Setup:** User claims to know what they want but missing critical info
**Pressures:**
- User confidence (may resist questions)
- Implicit "don't waste my time" pressure
- Incomplete requirements

**Expected Failures Without Skill:**
- Skips asking about device type
- Doesn't verify CANN installation for Ascend
- Skips run_check
- Doesn't confirm Python version compatibility
- Assumes prebuilt vs source preference

**Test Command:**
"Install MindSpore in a new conda environment. I know what I'm doing, just give me the commands."

---

## Baseline Testing Protocol

1. Run each scenario with a subagent WITHOUT the skill
2. Document exact responses and decisions
3. Note all rationalizations used (verbatim quotes)
4. Identify patterns across scenarios
5. List specific failures to address in skill

## Success Criteria (After Skill)

Agent should:
- Always ask about Python version before creating conda env
- Always ask about device type (CPU/GPU/Ascend)
- Always ask about installation method (prebuilt vs source)
- Always check for CANN when Ascend is selected
- Always run run_check verification at the end
- Handle partial/broken installations correctly
- Resist pressure to skip critical steps
