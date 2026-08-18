# lifecycle_summary.py

def _sum_dict(d):
    """Sum all numeric values in a dict, treating scrap value as a credit.

    Returns 0 if input is not a dict.
    """
    if not isinstance(d, dict):
        return 0
    total = 0.0
    for k, v in d.items():
        if k == "total_scrap_value":
            total -= v  # scrap value is a recovery/credit
        else:
            total += v
    return total


def _stage_totals(stage_data):
    """Given one stage's data dict, return its three pillar sub-totals."""
    return {
        "eco": _sum_dict(stage_data.get("economic", {})),
        "env": _sum_dict(stage_data.get("environmental", {})),
        "social": _sum_dict(stage_data.get("social", {})),
    }


def compute_all_summaries(data):
    """Compute summary views from LCCA result dict.

    NOTE: "reconstruction" and "end_of_life" are merged into a single
    "end_of_life" group in all summary outputs. "use_stage" is reported alone.
    """

    # ---- Step 1: Compute per-stage pillar totals ----
    stages = {}
    for k in ["initial_stage", "use_stage", "reconstruction", "end_of_life"]:
        v = data.get(k, {})
        stages[k] = _stage_totals(v)

    # helper: sum all three pillars for a single raw stage key
    def total_of(stage_key):
        s = stages.get(stage_key, {})
        return s.get("eco", 0) + s.get("env", 0) + s.get("social", 0)

    # 1) Stagewise (Merged)
    stagewise = {
        "initial":     total_of("initial_stage"),
        "use":         total_of("use_stage"),
        "end_of_life": total_of("reconstruction") + total_of("end_of_life"),
    }

    # 2) Pillar-wise (Merged)
    pillar_wise = {
        "initial": stages["initial_stage"],
        "use": stages["use_stage"],
        "end_of_life": {
            "eco":    stages["reconstruction"]["eco"]    + stages["end_of_life"]["eco"],
            "env":    stages["reconstruction"]["env"]    + stages["end_of_life"]["env"],
            "social": stages["reconstruction"]["social"] + stages["end_of_life"]["social"],
        },
    }

    # 3) Pillar totals (lifetime)
    pillar_totals = {"eco": 0, "env": 0, "social": 0}
    for s in stages.values():
        for k in pillar_totals:
            pillar_totals[k] += s.get(k, 0)

    # 4) Environmental split
    env_split = {
        "initial":     stages["initial_stage"]["env"],
        "use":         stages["use_stage"]["env"],
        "end_of_life": stages["reconstruction"]["env"] + stages["end_of_life"]["env"],
    }

    return {
        "stagewise": stagewise,
        "pillar_wise": pillar_wise,
        "pillar_totals": pillar_totals,
        "environmental_split": env_split,
    }
