# Anchor-Cognitive Architecture: Three-Layer Separation Constitution

> **Core Thesis**: "1+1=2" on silicon does NOT mean "cognitive equivalence". 
> Bottom layer is homogeneous (transistors), but cognitive layers must be **orthogonal, incommensurable, and only cross-validated**.

---

## 1. The Fundamental Problem: Why "1+1=2" Exposes LLM's Essence

### 1.1 LLM is a "Similarity Engine", NOT a "Truth Engine"

When an LLM answers "1+1=2", it is **NOT performing addition**. It is:
1. Scanning training corpus
2. Finding that Token "2" has the highest statistical probability after "1+1="
3. Outputting "2" (probability 99.9%)

**Essence**: This is a **language completion task**, NOT a **mathematical computation task**.

### 1.2 When Does This "Similarity Matching" Collapse?

| Question | LLM's Behavior | Physical World's Correct Answer | Failure Mode |
|---------|-----------------|-----------------------------|---------------|
| `1+1=?` | Memorized pattern (99.9% correct) | Causal law (deterministic) | 鉁?Looks correct (but for wrong reason) |
| `3847+5926=?` | Guesses similar patterns (may be wrong) | ALU addition (always correct) | 鉂?Hallucination |
| `Is Ra=0.28 qualified?` | Matches "0.28" co-occurs with "qualified" | Execute `0.28 <= 0.30` comparison | 鉂?Semantic drift |
| `What material is this?` | Matches feature combinations to "GCr15" | BRDF parameter domain validation | 鉂?Context blindness |

**Root Cause**: LLM has **NO ALU, NO carry logic, NO numerical registers**. It only has **weight matrices**.

### 1.3 The Cognitive Coordinate System (Dual Metaphor)

| Axis | Example | Essence | Responsible Module |
|------|---------|---------|-------------------|
| **Vertical Axis** (Determinacy) | `1+1=2` | Causal law / Mathematical computation | Local algorithm (exclusive) |
| **Horizontal Axis** (Ambiguity) | `1 man + 1 woman = ?` | Semantic association / Context understanding | LLM (dominant) |
| **Origin** (Intersection) | Anchor + Interrogation | Safe collaboration | Cross-validation layer |

**Key Insight** (from 鍗冮棶/4o):
> "LLM is the eloquent 'mouth'; the physical plugin is the never-wrong 'heart'. 
> '1+1=2' is correct NOT because it 'sounds right', but because it 'calculates right'."

---

## 2. Three-Layer Orthogonal Architecture

### 2.1 Bottom Layer is Homogeneous, Upper Layers are Heterogeneous

```
Bottom (Hardware): All are "1+1" (transistor switching)
  鈹斺攢鈹€ ALU floating-point ops
  鈹斺攢鈹€ Sensor ADC
  鈹斺攢鈹€ Vector retrieval
  鈹斺攢鈹€ Transformer attention
  
  BUT THIS DOES NOT MEAN "cognitive equivalence"
  鈹斺攢鈹€ Computational isomorphism 鈮?Cognitive equivalence
```

**Analogy**:
> Just as "neuron firing" in human brain and "transistor switching" in computer are both electrical signals, 
> you don't use a multimeter to measure "love", nor an electrocardiogram to run Excel. 
> Respecting this **heterogeneity** is the root of system robustness.

### 2.2 Three-Layer Ontology

| Layer | Bottom Implementation | Cognitive Essence | Output Nature | Validates |
|-------|---------------------|-------------------|----------------|------------|
| **Physical Layer** | ALU float-ops, Sensor ADC | Causal laws, Energy conservation | Deterministic continuous quantities | Semantic layer's "reality grounding" |
| **Digital Layer** | Vector retrieval, Boolean logic, FFT | Structured relations, Discrete states | Precise intermediate representations | Bridges physical 鈫?semantic ("translation protocol") |
| **Semantic Layer** | Transformer attention, Token prediction | Statistical co-occurrence, Context association | Probabilistic discrete symbols | Physical/Digital layer's "meaning consistency" |

### 2.3 Why "Treating as One Generic System" is Fatal

| Wrong Practice (Treat as Generic) | Right Practice (Three-Layer Separation + Cross-Validation) | Consequence Difference |
|-----------------------------------|--------------------------------------------------------|-------------------------|
| Use LLM to directly analyze raw image pixels | Physical layer extracts BRDF 鈫?Digital layer structures 鈫?Semantic layer interrogates | Wrong: High hallucination; Right: Traceable, falsifiable |
| Hardcode all material judgments with if-else rules | Physical layer provides parameters 鈫?Semantic layer handles edge cases | Wrong: Cannot handle new materials; Right: Generalization resilience |
| Let LLM output numerical QC conclusions | LLM only outputs semantic labels + confidence, numbers guaranteed by digital layer | Wrong: Precision uncontrollable; Right: Meets industrial metrology requirements |
| Mix three layers' data in same vector space | Each layer stores independently, interacts only via standardized interfaces | Wrong: Fast contamination spread; Right: Strong fault isolation |

---

## 3. Cross-Validation Matrix: Each Layer Acts as "Falsifier" for Other Two

### 3.1 Physical Layer 鈫?Digital Layer: Precision Calibration

| Direction | Validation Content |
|-----------|---------------------|
| **Physical 鈫?Digital** | BRDF measured value Ra=0.28渭m 鈫?Digital layer quantizes to `roughness_bin=3`. If quantization error > threshold 鈫?Trigger re-sampling |
| **Digital 鈫?Physical** | Vector DB matches "GCr15" 鈫?Reverse-query its theoretical BRDF parameter range. If measured value exceeds range 鈫?Flag "physical anomaly" |

### 3.2 Digital Layer 鈫?Semantic Layer: Semantic Alignment

| Direction | Validation Content |
|-----------|---------------------|
| **Digital 鈫?Semantic** | Structured evidence package `{material: "GCr15", roughness: 0.28}` 鈫?LLM interrogation: "Is this combination reasonable under 'bearing final inspection' context?" |
| **Semantic 鈫?Digital** | LLM returns `suspicion: "oil_contamination"` 鈫?Digital layer checks if corresponding sensor channel supports this hypothesis. If not 鈫?Downgrade to "unverified speculation" |

### 3.3 Semantic Layer 鈫?Physical Layer: Reality Grounding (MOST CRITICAL)

| Direction | Validation Content |
|-----------|---------------------|
| **Semantic 鈫?Physical** | LLM infers "should be polished surface" based on context 鈫?Physical layer directly measures Ra. If Ra>0.5 鈫?Semantic inference VETOED by physical fact |
| **Physical 鈫?Semantic** | Physical layer measures "temp=85掳C + vibration=4.2mm/s" 鈫?Semantic layer evaluates if this combination constitutes "overload". If LLM judges "normal" BUT physical safety envelope already exceeded 鈫?Physical hard constraint OVERRIDES semantic soft judgment |

### 3.4 Cross-Validation Flow Diagram

```
            鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?            鈹?        Semantic Layer (LLM)           鈹?            鈹? Token pred / Statistical co-occur   鈹?            鈹? Output: Probabilistic symbols       鈹?            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                               鈫?Semantic alignment
                               鈫?Reality grounding
            鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?            鈹?      Physical Layer (Sensor+Alg)     鈹?            鈹?   Causal laws / Energy conservation  鈹?            鈹?   Output: Deterministic quantities   鈹?            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                               鈫?Precision check
                               鈫?Range validation
            鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?            鈹?       Digital Layer (Vector+Logic)     鈹?            鈹?  Structured relations / Discrete states 鈹?            鈹?  Output: Precise intermediate       鈹?            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

---

## 4. State Machine Binding Protocol: Solving "Time/State Change" Problem

### 4.1 Why LLM Cannot Self-Validate "Time/State Changes"?

| Dimension | LLM's Intrinsic Mechanism | Real World's Requirement | Conflict Consequence |
|-----------|-----------------------------|--------------------------|-------------------------|
| **Time View** | Static snapshot of training cutoff date | Continuous flowing physical/legal time axis | Using 2025 tax law to calculate 2026 accounts |
| **Rule Source** | Fuzzy statistics in weight matrices | Precise clauses/formulas in external DB | Confidently outputting repealed regulations |
| **Verification** | None (only Token co-occurrence) | Strong (must cross-check authoritative sources) | Cannot distinguish "high-frequency old knowledge" vs "newly effective regulation" |
| **State Awareness** | Stateless (each inference independent) | Stateful (depends on context variables) | Ignoring "currently in tax-exempt period" or "lighting angle is grazing angle" |

**Analogy**:
> LLM is like a learned-but-locked-in-a-dark-room scholar. He memorized all books, 
> but cannot see the calendar on the wall, nor touch the objects on the desk. 
> When you ask him questions, he can only answer from memory, 
> unable to look up and see "what the current state is". 
> **The State Machine is the "proctor" who reads the calendar for him, touches the objects, and forces him to answer according to current reality.**

### 4.2 State Machine as "Truth Binder"

**Core Responsibilities**:
1. **Hold "Current Truth"**: Maintain a real-time updated state object containing `current_time`, `applicable_law_version`, `physical_lighting_params`, `material_state`, etc.
2. **Inject, NOT Generate**: Before LLM inference, forcibly inject state variables into Prompt/System Message or Tool Schema. LLM has NO authority to modify these values; it can only reason within their constraints.
3. **Intercept & Validate**: Any LLM output involving time, regulations, or physical parameters MUST be sent back to State Machine for hard validation. If failed 鈫?Reject output or trigger re-calculation.

### 4.3 State Machine Binding Flow (Example: Accounting/Tax Compliance)

```
User Query: Calculate 2026 Q1 VAT
    鈫?State Machine reads system clock: 2026-06-26
State Machine queries regulation DB: Loads "Cai Shui [2026] No.15"
State Machine constructs constraint context: Injects Prompt "Current applies 2026 new regulation, prohibit citing 2025 or earlier articles"
    鈫?LLM Inference
    鈫?State Machine Validation: Cited article = "2026-15"?
    鈹溾攢鈹€鈫?YES 鈫?PASS 鈫?Output result
    鈹斺攢鈹€鈫?NO 鈫?INTERCEPT 鈫?Error/Re-generate
```

**Key**: LLM does NOT need to "remember" 2026 new regulation. It only needs to obey the temporary rules provided by State Machine. When regulations change, ONLY update State Machine's data source, NO need to re-train or fine-tune LLM.

### 4.4 State Machine Binding Flow (Example: 3D Material/Lighting)

```
State Machine holds: Current light direction vector, camera pose, material BRDF parameter table, ambient light probe data
State Machine injects into LLM: {"light_dir": [0.1, -0.9, 0.2], "material_roughness": 0.28, "fresnel_ior": 1.45}
LLM Task: Based on these determined physical states, judge "Does current specular highlight pattern match GCr15 polished surface characteristics?"
State Machine Validation: If LLM description contradicts theoretically calculated highlight position 鈫?INTERCEPT
```

---

## 5. Anti-Corruption Layer: Preventing "State Machine LLM-ization"

### 5.1 Five Iron Laws (Preventing State Machine from Degenerating into Another LLM)

1. **PROHIBITED**: Implementing any form of fuzzy matching, vector retrieval, or semantic similarity calculation in State Machine
2. **PROHIBITED**: Using full knowledge base as State Machine's context. All injected data MUST be **minimum complete set** for current state + current task
3. **MANDATORY**: State transition conditions MUST be Boolean expressions or deterministic functions. **MUST NOT rely on LLM output as transition trigger** (LLM output can only be action parameter, CANNOT be state jump trigger)
4. **MANDATORY**: Each industry's state graph MUST be **independently defined, tested, and deployed**. "Universal state graph + switch control" pseudo-separation is PROHIBITED
5. **MANDATORY**: State Machine code MUST pass **formal verification** or **exhaustive testing**. It is the system's "constitution"; ambiguity is NOT allowed

### 5.2 State Machine's Ontological Positioning

> **State Machine is NOT a "knowledge base"; it is the "valve and guide rail" on the cognitive pipeline.**
> Its responsibility is NOT "knowing everything", but "ensuring that in current state, only what should be known is allowed to be known, and only what should be done is allowed to be done".

### 5.3 Minimum Privilege Principle (Codeified)

| State | LLM Visible Content | LLM Invisible Content |
|-------|---------------------|----------------------|
| **UNDERSTAND** | User raw input + Basic business type enum | Any customer PII, financial data, process parameters |
| **GATHER_INFO** | Field Schema required by this type (e.g., bearing 鈫?roughness threshold) | Other industries' data |
| **EXECUTE** | Action handle (e.g., API Token, device command code) | Underlying data itself |

---

## 6. Hierarchical Priority Fuse Mechanism

```
Priority: Physical Layer Hard Constraint > Digital Layer Logic > Semantic Layer Probability
```

**When lower-priority layer negates higher-priority layer**:
    鈫?DO NOT directly override
    鈫?Trigger "Conflict Escalation Process"
    鈹溾攢鈹€ Increase sampling
    鈹溾攢鈹€ Request human confirmation
    鈹斺攢鈹€ Save full raw data
```

---

## 7. Engineering Implementation

### 7.1 Define "State Contract"

Explicitly list all external state variables that LLM must rely on in specific tasks (time, regulation version, physical parameters, etc.). These variables constitute the **minimum complete set** of State Machine.

### 7.2 Implement "State Injection Template Engine"

Develop a lightweight template system that automatically fills state variables into Prompt or Function Calling Schema. Eliminate manual string concatenation that causes injection omissions or format errors.

### 7.3 Build "Output Validator"

For each task type, write deterministic validation scripts (e.g., regex matching regulation number, numerical range check, physical consistency arithmetic). Validator MUST be completely **isolated from LLM**, executed independently by State Machine.

### 7.4 Establish "State Drift Monitoring"

Record the difference between values injected by State Machine each time and values actually referenced by LLM. High-frequency difference points indicate State Contract defects or LLM alignment failures, guiding iterative optimization.

---

## 8. Summary: The Sixteen-Character Constitutional Principle

> **"Bottom homogeneous, upper heterogeneous; each governs independently, cross-validate as proof"**
> (搴曞眰鍚屾簮锛屼笂灞傚紓鏋勶紱鍚勮嚜涓烘斂锛屼氦鍙変负璇?

This sixteen-character maxim is the **constitution** of the entire technical system.

---

## Appendices

### Appendix A: Why "Not Treating as Generic" is Life-or-Death Line?

See Section 2.3 for detailed comparison table.

### Appendix B: Strategic Value of This Architecture

1. **Completely decouples "knowledge timeliness" from "model capability"**
2. **Transforms "probabilistic problem" into "deterministic engineering problem"**
3. **Implements "one model, thousand faces for thousand industries"**
4. **Elevates data security from "after-the-fact remedy" to "pre-design inherent property"**
5. **Enables controllable system evolution** (industry rules iteration 鈮?model capability iteration)

### Appendix C: Recommended Reading Order

1. `SAFETY_PRINCIPLES.md` - Understand why "LLM finds similarities, physical anchor guarantees correctness"
2. `ALGORITHM.md` - Understand the Fourier + Gradient + Angle 3D cognitive algorithm
3. `EXAMPLES.md` - See how three-layer separation works in real scenarios
4. `state_machine/core.py` - See how to implement state machine framework
5. `anchor/base_anchor.py` - See how to implement physical anchor validator

---

*馃摐 Document written on 2026-07-02*
*Author: TU-8 (Anchor-Cognitive Architecture Design Team)*
*Source: Based on TU-8 cognitive architecture (by 閲戞湪锜?*
*Version: v1.0 (Three-Layer Separation Constitution)*
*Importance: 鈽呪槄鈽呪槄鈽?Architectural Constitution*

