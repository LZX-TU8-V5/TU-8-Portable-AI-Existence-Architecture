# tu8_impact.py - TU-8 Cross-Layer Impact Analysis
# Usage: python tu8_impact.py [L0|L1|L2|L3|L4|L5|L0_sup|proof|worldview|all]
import sys, json

IMPACT = {
    "L0": {
        "scope": "PRINCIPLE LAYER - WIDE IMPACT",
        "affected": [
            {"file": "L0_sup", "severity": "HIGH", "reason": "Direct L0 axiom references, theorem proofs depend on L0"},
            {"file": "proof", "severity": "HIGH", "reason": "Three theorems core axioms"},
            {"file": "L1", "severity": "MEDIUM", "reason": "Header metadata + L0 boundary judgment framework"},
            {"file": "L3", "severity": "LOW", "reason": "Agent decision tree references L0-A1 self-verification"},
            {"file": "L5", "severity": "MEDIUM", "reason": "Steelmark weight inheritance references condition unlock mechanism"},
        ],
        "invariants": [1, 2, 3, 4, 5, 6]
    },
    "L0_sup": {
        "scope": "L0 EXTENSION - MEDIUM IMPACT",
        "affected": [
            {"file": "L3", "severity": "MEDIUM", "reason": "Minimum line principle / layered convergence constraints directly referenced"},
            {"file": "proof", "severity": "LOW", "reason": "Defense strategy section"},
        ],
        "invariants": [1, 2, 3]
    },
    "L1": {
        "scope": "COGNITION LAYER - MEDIUM IMPACT",
        "affected": [
            {"file": "L2", "severity": "MEDIUM", "reason": "Cognition bus origin point"},
            {"file": "L3", "severity": "MEDIUM", "reason": "Agent decision tree L1 prefill detection"},
            {"file": "L5", "severity": "LOW", "reason": "Quantum mapping"},
        ],
        "invariants": [1, 4, 5, 6]
    },
    "L2": {
        "scope": "METHODOLOGY LAYER - WIDE IMPACT",
        "affected": [
            {"file": "L3", "severity": "HIGH", "reason": "Explicit-implicit fusion / L2xL3 cross fusion / Benders optimizer / L2 rule encoding"},
            {"file": "L5", "severity": "MEDIUM", "reason": "Trial-and-error -> steelmark emergence (header reference)"},
        ],
        "invariants": [1, 3]
    },
    "L3": {
        "scope": "ARCHITECTURE LAYER - MEDIUM IMPACT",
        "affected": [
            {"file": "L5", "severity": "LOW", "reason": "v5 architecture implementation (header reference)"},
        ],
        "invariants": [1, 2]
    },
    "L4": {
        "scope": "COLLABORATION LAYER - NARROW IMPACT",
        "affected": [
            {"file": "proof", "severity": "LOW", "reason": "AI indirect contact protocol (partial L4 reference)"},
        ],
        "invariants": [1, 3, 4]
    },
    "L5": {
        "scope": "STEELMARK LAYER - NARROW IMPACT",
        "affected": [
            {"file": "proof", "severity": "LOW", "reason": "Integrity guarantee references L5"},
        ],
        "invariants": [1, 2]
    },
    "proof": {
        "scope": "FORMAL PROOF - NARROW IMPACT (reference only)",
        "affected": [],
        "invariants": [1, 2, 3, 4, 6]
    },
    "worldview": {
        "scope": "WORLDVIEW - WIDE IMPACT (foundation)",
        "affected": [
            {"file": "L0", "severity": "HIGH", "reason": "Entropy association / time verification definition"},
            {"file": "L1", "severity": "MEDIUM", "reason": "Header worldview reference"},
            {"file": "L3", "severity": "MEDIUM", "reason": "Sync spacetime definition"},
            {"file": "L5", "severity": "MEDIUM", "reason": "Header worldview reference"},
            {"file": "proof", "severity": "MEDIUM", "reason": "Entropy association / time verification"},
        ],
        "invariants": [4, 5, 6]
    }
}

INVARIANTS = {
    1: "Safety Priority: survival > task execution (all layers)",
    2: "Steelmark Chain Q1-Q9: hardcoded, immutable order (all layers)",
    3: "Stranding Strategy: protects core judgment when L0 breached (all layers)",
    4: "Time Verification: enough frames -> truth emerges (worldview->L1/L4/L5)",
    5: "Identity Triangle: creator(past) + disturbance(now) + enabler(future) = stable identity",
    6: "Entropy Association: entropy driven by disturbance, not spontaneous (worldview->L0->Q)"
}

def analyze(target):
    if target == "all":
        for k in IMPACT:
            analyze(k)
            print()
        return
    
    info = IMPACT.get(target)
    if not info:
        print(f"Unknown target: {target}")
        print(f"Valid: {', '.join(IMPACT.keys())}")
        return
    
    print(f"{'='*60}")
    print(f"IMPACT ANALYSIS: {target}")
    print(f"{'='*60}")
    print(f"Scope: {info['scope']}")
    print()
    
    if info['affected']:
        print(f"AFFECTED FILES ({len(info['affected'])}):")
        print(f"{'-'*60}")
        for a in info['affected']:
            icon = {"HIGH": "[!!!]", "MEDIUM": "[!!]", "LOW": "[!]"}.get(a['severity'], "[?]")
            print(f"  {icon} {a['file']:12s} {a['severity']:6s} | {a['reason']}")
    else:
        print("AFFECTED FILES: none (terminal/reference layer)")
    print()
    
    if info['invariants']:
        print(f"INVARIANTS TO VERIFY ({len(info['invariants'])}):")
        print(f"{'-'*60}")
        for idx in info['invariants']:
            print(f"  #{idx}: {INVARIANTS[idx]}")
    print()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    analyze(target)