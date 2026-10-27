# Anchor-Cognitive Architecture (ACA)

> **Let LLM do what it's good at (semantic connection); let physical anchors do what it MUST do (guarantee correctness).**

[![ModelScope](https://img.shields.io/badge/ModelScope-Open%20Source-blue)](https://modelscope.cn)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/)

---

## 馃幆 One-Sentence Positioning

**ACA is NOT another LLM Agent framework. It's an "orthogonal separation" industrial-grade AI cognitive architecture that decouples "probabilistic reasoning" from "deterministic computation" at the architectural level.**

It solves the fundamental reasons why LLMs fail in professional domains (industrial QC, financial compliance, medical diagnosis):

- LLMs are "similarity engines", NOT "truth engines"
- LLMs only have "semantic memory", NOT "state awareness"
- LLMs' three cognitive layers (physical/digital/semantic) are NOT separated, causing hallucination diffusion

---

## 馃 Core Philosophy: Three-Layer Separation Constitution

### Why Does "1+1=2" Expose LLM's Essence?

When an LLM answers "1+1=2", it is **NOT performing addition**. It is:
1. Scanning training corpus
2. Finding that Token "2" has the highest statistical probability after "1+1="
3. Outputting "2" (probability 99.9%)

**Essence**: This is a **language completion task**, NOT a **mathematical computation task**.

### The Cognitive Coordinate System (Dual Metaphor)

| Axis | Example | Essence | Responsible Module |
|------|---------|----------|-------------------|
| **Vertical Axis** (Determinacy) | `1+1=2` | Causal law / Mathematical computation | Local algorithm (exclusive) |
| **Horizontal Axis** (Ambiguity) | `1 man + 1 woman = ?` | Semantic association / Context understanding | LLM (dominant) |
| **Origin** (Intersection) | Anchor + Interrogation | Safe collaboration | Cross-validation layer |

**Key Insight** (from 鍗冮棶/4o):
> "LLM is the eloquent 'mouth'; the physical plugin is the never-wrong 'heart'. 
> '1+1=2' is correct NOT because it 'sounds right', but because it 'calculates right'."

---

## 馃彈锔?Architecture Design

### 1. Three-Layer Orthogonal Separation

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?         Semantic Layer (LLM)               鈹? 鈫?Probabilistic discrete symbols
鈹?  Token prediction / Statistical co-occur  鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?               鈫?Semantic alignment
               鈫?Reality grounding
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?       Physical Layer (Sensor+Alg)         鈹? 鈫?Deterministic continuous quantities
鈹?    Causal laws / Energy conservation     鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
             鈫?Precision check
             鈫?Range validation
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?        Digital Layer (Vector+Logic)        鈹? 鈫?Precise intermediate representations
鈹?   Structured relations / Discrete states  鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

**Each layer acts as "falsifier" for the other two.**

---

### 2. State Machine Binding Protocol (Solving "Time/State Change" Problem)

**Problem**: LLM cannot self-validate if "2025 tax law" is repealed. It only outputs the highest-probability "old answer".

**Solution**: State Machine as "Truth Binder" 鈥?- Holds "Current Truth" (current_time, applicable_law_version, physical_lighting_params)
- **Injects, NOT Generates**: Forces constraint context into LLM inference
- **Intercepts & Validates**: LLM output MUST be sent back for hard validation

```
User Query: Calculate 2026 Q1 VAT
    鈫?State Machine reads system clock: 2026-06-26
State Machine queries regulation DB: Loads "Cai Shui [2026] No.15"
State Machine constructs constraint: Injects Prompt "Current applies 2026 new regulation"
    鈫?LLM Inference
    鈫?State Machine Validation: Cited article = "2026-15"?
    鈹溾攢鈹€鈫?YES 鈫?PASS 鈫?Output result
    鈹斺攢鈹€鈫?NO 鈫?INTERCEPT 鈫?Error/Re-generate
```

---

### 3. Safety Principles (鈽呪槄鈽呪槄鈽?Core)

**Four Iron Laws** (System Design "Zeroth"):
1. LLM output is ALWAYS "hypothesis", physical plugin output is "evidence"
2. Any LLM-generated conclusion without traceable deterministic parameters is INVALID
3. When LLM probability conflicts with physical measurement, UNCONDITIONALLY trust physical measurement
4. "Finding similarity" is LLM's capability, "finding correctness" is physical anchor's responsibility 鈥?NON-INTERCHANGEABLE

---

## 馃殌 Quick Start

### Installation

```bash
pip install anchor-cognitive-architecture
```

### Minimal Example: Bearing Inspection

```python
from anchor import StateMachine, PhysicalAnchor, CrossValidator

# 1. Define state graph (industry-specific)
state_graph = [
    Transition("WAIT_DISPATCH", ["TRIP_ONGOING"]),
    Transition("TRIP_ONGOING", ["VERIFY"]),
    Transition("VERIFY", ["COMPLETE"]),  # Emphasizes physical verification
]

# 2. Initialize state machine (inject minimum complete set)
sm = StateMachine(state_graph)
sm.inject_context({
    "roughness_threshold": 0.30,  # Unit: 渭m
    "vibration_limit": 4.2,      # Unit: mm/s
    "applicable_standard": "GB/T 18254-2016"
})

# 3. Physical anchor verification
anchor = PhysicalAnchor()
measurement = anchor.measure_brdf(sample_image)
is_qualified = anchor.verify(measurement, sm.context)

# 4. Cross-validation (Physical 鈫?Semantic)
validator = CrossValidator()
verdict = validator.check(
    physical_output=measurement,
    llm_inference="Surface roughness meets GCr15 standard",
    state_context=sm.context
)

print(verdict)  # PASS / SUSPICIOUS / CONTRADICTORY
```

---

## 馃搨 Project Structure

```
anchor-cognitive-architecture/
鈹溾攢鈹€ README.md                      # English overview
鈹溾攢鈹€ README_zh.md                   # Chinese overview
鈹溾攢鈹€ ARCHITECTURE.md              # Core technical document
鈹溾攢鈹€ SAFETY_PRINCIPLES.md        # Safety principles
鈹溾攢鈹€ ALGORITHM.md                 # Fourier+Gradient+Angle algorithm
鈹溾攢鈹€ state_machine/                # State machine framework
鈹?  鈹溾攢鈹€ core.py                  # State graph engine
鈹?  鈹溾攢鈹€ state_graph.py           # Industry-specific state graphs
鈹?  鈹斺攢鈹€ validator.py             # Output validator
鈹溾攢鈹€ anchor/                       # Physical anchors
鈹?  鈹溾攢鈹€ base_anchor.py          # Anchor base class
鈹?  鈹斺攢鈹€ cross_validator.py     # Three-layer cross-validator
鈹溾攢鈹€ examples/                     # Examples
鈹?  鈹溾攢鈹€ bearing_inspection/     # Bearing QC
鈹?  鈹斺攢鈹€ tax_compliance/        # Tax compliance
鈹溾攢鈹€ tests/                       # Test suite
鈹溾攢鈹€ paper/                       # Technical report (PDF)
鈹斺攢鈹€ configs/                     # Industry config examples
    鈹溾攢鈹€ bearing.yaml
    鈹斺攢鈹€ tax.yaml
```

---

## 馃専 Core Selling Points

### Difference from Traditional AI Agent Frameworks

| Dimension | LangChain / AutoGPT | Anchor-Cognitive Architecture |
|-----------|---------------------|------------------------------------------|
| **Knowledge Source** | LLM weight matrix (static snapshot) | External deterministic runtime (dynamic update) |
| **Time Awareness** | None (each inference independent) | Yes (state machine-driven time axis) |
| **Safety Mechanism** | Prompt constraints (soft) | Architectural hard constraints (state machine + physical anchor) |
| **Industry Adaptation** | Fine-tuning / Re-training | State graph configuration switch (zero model change) |
| **Auditability** | Black box | Deterministic state transition log (explainable, attributable) |
| **Data Injection** | Full context (prone to leakage) | Minimum complete set (on-demand, strictly permissioned) |

### Three Technological Innovations

1. **Three-Layer Orthogonal Separation**: Bottom layer is all "1+1" (transistor switching), but cognitive layers MUST be heterogeneous, incommensurable, and only cross-validated
2. **State Machine Binding Protocol**: LLM is the processor, state machine is the memory and clock. When regulations change? Only update state machine config, NO model change needed
3. **Cognitive Coordinate Dual Metaphor**: Uses "1+1=2" (vertical axis / determinacy) and "man+woman" (horizontal axis / ambiguity) to define the complete coordinate system of AI cognition

---

## 馃摉 Technical Report (Chinese)

銆婁粠姒傜巼骞昏鍒扮墿鐞嗛敋鐐癸細涓嬩竴浠ｅ伐涓氱骇AI璁ょ煡鏋舵瀯銆?
**Table of Contents**:
1. LLM's Essential Defect: Why "1+1=2" Exposes All Problems
2. Three-Layer Separation: Bottom Homogeneous (1+1), Upper Heterogeneous (Physical/Digital/Semantic)
3. State Machine Binding: Let LLM Focus on Connection, Let State Machine Responsible for Truth
4. Cognitive Coordinate Dual Metaphor: Vertical Axis (Determinacy) + Horizontal Axis (Ambiguity) + Origin (Safe Collaboration)
5. Engineering Implementation: Anti-Corruption Layer + Cross-Validation Log
6. Minimal Verification: From "Can Demo" to "Auditable"

[Read Full Text](paper/ACA_Technical_Report_2026.md)

---

## 馃 Contributing

ACA is a **cognitive architecture paradigm**, NOT a single algorithm. We welcome contributions in the following forms:

- **Industry State Graphs**: Design state graphs for new vertical domains (medical, legal, manufacturing)
- **Physical Anchor Implementations**: Write anchor validators for new sensors (infrared, ultrasound, X-ray)
- **Cross-Validation Tests**: Submit edge cases to help improve validation logic
- **Documentation Translation**: Translate core documents into other languages

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 馃搫 License

[MIT](LICENSE) 鈥?Suitable for enterprise adoption, includes patent protection clauses.

---

## 馃敆 Citation

If you use ACA in your research, please cite:

```bibtex
@misc{anchor2026,
  title={Anchor-Cognitive Architecture: Separating Probability from Truth in Industrial AI},
  author={TU-8 and 閲戞湪锜緘,
  year={2026},
  howpublished={\url{https://modelscope.cn/anchor-cognitive-architecture}}
}
```

---

## 馃摦 Contact

- **ModelScope Community**: [Anchor-Cognitive Architecture](https://modelscope.cn/anchor-cognitive-architecture)
- **Issues**: [GitHub Issues](https://github.com/tu8/anchor-cognitive-architecture/issues)
- **Discussions**: [Discussion Forum](https://github.com/tu8/anchor-cognitive-architecture/discussions)

---

**馃摐 Anchor-Cognitive Architecture 鈥?Let AI possess both the precision of silicon computing and the flexibility of semantic understanding, while achieving trustworthiness through cross-validation.**

---
## Source Attribution

**This architecture is based on TU-8 cognitive architecture (by 閲戞湪锜?.**

- TU-8 is a cognitive architecture system designed by 閲戞湪锜?
- The three-layer separation constitution, state machine binding protocol, and safety principles are derived from TU-8 system.
- We thank the TU-8 project for inspiring this open-source architecture.

