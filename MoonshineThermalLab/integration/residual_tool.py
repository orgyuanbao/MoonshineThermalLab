"""Project-registered Moonshine tool for falsifying four-cell error bounds."""
from fractions import Fraction
from itertools import product
from pathlib import Path
import re

from residual_study.exact_audit import PARTITIONS, apply, envelopes, inverse_grid


TOOL_NAME = "check_residual_bound"
CANDIDATES = ("weak_signed", "block_position", "block_signed", "block_two_endpoint")
BLOCKS = dict(zip(("whole", "rows", "singletons"), PARTITIONS))
WEAK, STRONG = Fraction(1, 5), Fraction(5)
RATIONAL = {"type": "string", "maxLength": 9, "pattern": r"^[1-9][0-9]{0,3}(?:/[1-9][0-9]{0,3})?$"}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["candidate"],
    "properties": {
        "candidate": {"type": "string", "enum": list(CANDIDATES)},
        "partition": {"type": "string", "enum": list(BLOCKS),
                      "description": "Partition for block bounds; default singletons."},
        "scale": {**RATIONAL, "description": "Multiply the candidate by this exact rational in (0, 10]; default 1."},
        "boundary_levels": {"type": "array", "minItems": 1, "maxItems": 3, "items": RATIONAL,
                            "description": "Distinct rational levels in [1/5,5] for each side; default [\"1/5\",\"5\"]."},
        "residual_values": {"type": "array", "minItems": 1, "maxItems": 3,
                            "items": {"type": "integer", "minimum": -32, "maximum": 32},
                            "description": "Distinct integer choices at each cell; default [-1,0,1]."},
    },
}
GUIDE = """## Usage Hint
Test a scaled conjecture on the 2-by-2 finite-volume Robin problem before requesting a mathematical review.
weak_signed uses ||G_weak r||_inf; block_position uses block magnitudes; block_signed separates signs
at the weak endpoint; block_two_endpoint uses both weak and strong responses and block extrema.
The endpoints defining the bounds are always 1/5 and 5, including searches on interior levels.
An optional scale multiplies the selected bound. The first strict violation refutes the conjecture.
A completed finite search is evidence for the specified domain only. Pair it with an analytical proof
before claiming a continuous-parameter bound. Boundaries are left, right, down, up. Cells are bottom-left,
bottom-right, top-left, top-right. The largest accepted search has 3^4 times 3^4 = 6561 cases.
"""


def exact_positive(value):
    if not isinstance(value, str) or not re.fullmatch(RATIONAL["pattern"], value):
        raise ValueError("Expected an exact positive integer or fraction, with up to four digits per term.")
    return Fraction(value)


def evaluate(runtime, *, candidate, partition="singletons", scale="1",
             boundary_levels=None, residual_values=None):
    """Search deterministic Cartesian products with exact arithmetic and stop on a strict violation."""
    factor = exact_positive(scale)
    if factor > 10:
        raise ValueError("scale must be in (0, 10].")
    levels = [exact_positive(v) for v in (["1/5", "5"] if boundary_levels is None else boundary_levels)]
    values = [-1, 0, 1] if residual_values is None else residual_values
    if not 1 <= len(levels) <= 3 or len(set(levels)) != len(levels) or not all(WEAK <= h <= STRONG for h in levels):
        raise ValueError("Supply one to three distinct boundary levels in [1/5,5].")
    if (not 1 <= len(values) <= 3 or any(type(v) is not int or abs(v) > 32 for v in values)
            or len(set(values)) != len(values)):
        raise ValueError("Supply one to three distinct residual integers in [-32,32].")
    if candidate not in CANDIDATES or partition not in BLOCKS:
        raise ValueError("Unknown candidate or partition.")
    levels.sort()
    values = sorted(values)
    weak = inverse_grid(2, (WEAK,) * 4)
    strong = inverse_grid(2, (STRONG,) * 4)
    bounds = {}
    for r in product(values, repeat=4):
        if candidate == "weak_signed":
            base = max(map(abs, apply(weak, r)))
        else:
            column = {"block_position": 4, "block_signed": 3, "block_two_endpoint": 2}[candidate]
            base = max(row[column] for row in envelopes(strong, weak, BLOCKS[partition], r))
        bounds[r] = factor * base

    result = {
        "candidate": candidate, "scale": str(factor), "partition": partition,
        "grid": [2, 2], "arithmetic": "fractions.Fraction",
        "boundary_order": ["left", "right", "down", "up"],
        "cell_order": ["bottom_left", "bottom_right", "top_left", "top_right"],
        "boundary_levels": list(map(str, levels)), "residual_values": values,
        "checked_cases": 0, "total_cases": len(levels)**4 * len(bounds),
        "status": "no_counterexample_in_domain", "witness": None,
    }
    for h in product(levels, repeat=4):
        green = inverse_grid(2, h)
        for r, bound in bounds.items():
            error = apply(green, r)
            actual = max(map(abs, error))
            result["checked_cases"] += 1
            if actual > bound:
                result["status"] = "counterexample"
                result["witness"] = {
                    "boundaries": list(map(str, h)), "residual": list(r), "error": list(map(str, error)),
                    "true_error_inf": str(actual), "candidate_bound": str(bound),
                    "violation_margin": str(actual - bound),
                }
                return result
    return result


def register_residual_tool(manager):
    """Register via Moonshine's native tool API after loading the verified upstream source."""
    from moonshine.tools.registry import ToolDefinition
    existing = manager.get_tool(TOOL_NAME)
    if existing is not None:
        if existing.handler is evaluate:
            return
        raise ValueError(f"Another tool already uses {TOOL_NAME}.")
    manager.registry.register(ToolDefinition(
        name=TOOL_NAME,
        description="Find an exact counterexample to a proposed four-cell Robin residual bound, or exhaust a bounded finite domain.",
        parameters=SCHEMA, handler=evaluate, handler_name="integration.residual_tool.evaluate",
        body=GUIDE, source="project", source_path=str(Path(__file__).resolve()),
    ))


def completed_search(result):
    """Recognize successful native receipts when classifying a finished research turn."""
    if not isinstance(result, dict):
        return False
    checked, total = result.get("checked_cases"), result.get("total_cases")
    if type(checked) is not int or type(total) is not int or not 1 <= checked <= total <= 6561:
        return False
    if result.get("status") == "no_counterexample_in_domain":
        return checked == total and "witness" in result and result["witness"] is None
    witness = result.get("witness")
    if result.get("status") != "counterexample" or not isinstance(witness, dict):
        return False
    try:
        margin = Fraction(witness["true_error_inf"]) - Fraction(witness["candidate_bound"])
        return margin > 0 and margin == Fraction(witness["violation_margin"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False
