"""Residual certificates for nonnegative inverse thermal matrices, fixed 4 x 4 blocks."""
from time import perf_counter

import numpy as np
from scipy.sparse.linalg import splu


NAMES = ("analytic", "sharp_scalar", "block_abs", "block_sign", "two_endpoint")
BLOCKS_PER_AXIS = 4


class Certificates:
    """Grid-only data prepared before seeing a query or its reduced solution."""

    def __init__(self, geometry):
        self.geometry = geometry
        n, k = geometry.n, BLOCKS_PER_AXIS
        if n % k:
            raise ValueError("This protocol uses equal 4-by-4 blocks; n must be divisible by 4.")
        self.n = n
        self.block_width = n // k
        partition_started = perf_counter()
        rows, cols = np.indices((n, n))
        labels = (rows // self.block_width * k + cols // self.block_width).ravel()
        indicators = np.asfortranarray(labels[:, None] == np.arange(k*k), dtype=float)
        self.preparation = {"partition_and_rhs_s": perf_counter() - partition_started}

        def endpoint(h, label):
            start = perf_counter()
            matrix = geometry.matrix([h]*4).tocsc()
            factor = splu(matrix)
            self.preparation[label + "_factor_s"] = perf_counter() - start
            return matrix, factor

        weakest, weak_lu = endpoint(0.2, "weak")
        start = perf_counter()
        uniform_response = weak_lu.solve(np.ones(n*n))
        self.sharp_constant = float(np.max(uniform_response))
        self.preparation["unit_rhs_s"] = perf_counter() - start
        start = perf_counter()
        self.upper_response = np.ascontiguousarray(weak_lu.solve(indicators))
        self.preparation["upper_responses_s"] = perf_counter() - start
        strongest, strong_lu = endpoint(5.0, "strong")
        start = perf_counter()
        self.lower_response = np.ascontiguousarray(strong_lu.solve(indicators))
        self.preparation["lower_responses_s"] = perf_counter() - start
        self.coefficient_checks = {
            "min_lower_response_entry": float(self.lower_response.min()),
            "min_upper_minus_lower_response": float((self.upper_response-self.lower_response).min()),
            "max_template_equation_residual": max(float(np.max(abs(weakest@self.upper_response-indicators))),
                                                   float(np.max(abs(strongest@self.lower_response-indicators)))),
            "max_sum_upper_minus_unit_response_abs": float(np.max(abs(self.upper_response.sum(axis=1)-uniform_response))),
            "unit_rhs_sharpness_witness": self.sharp_constant,
            "analytic_constant": float(geometry.zmax),
        }
        if (self.coefficient_checks["min_lower_response_entry"] < -1e-10 or
                self.coefficient_checks["min_upper_minus_lower_response"] < -1e-10 or
                self.coefficient_checks["max_template_equation_residual"] > 1e-8 or
                self.coefficient_checks["max_sum_upper_minus_unit_response_abs"] > 1e-7):
            raise ArithmeticError("Offline endpoint check failed")
        # Separate costs for a hypothetical deployment of just one estimator.
        weak = self.preparation["weak_factor_s"]
        blocks = self.preparation["partition_and_rhs_s"] + weak + self.preparation["upper_responses_s"]
        self.offline = {
            "analytic": geometry.barrier_seconds,
            "sharp_scalar": weak + self.preparation["unit_rhs_s"],
            "block_abs": blocks, "block_sign": blocks,
            "two_endpoint": blocks + self.preparation["strong_factor_s"] + self.preparation["lower_responses_s"],
        }
        self.templates_bytes = self.upper_response.nbytes

    def extrema(self, residual):
        k, d = BLOCKS_PER_AXIS, self.block_width
        tiled = np.asarray(residual).reshape(k, d, k, d)
        return tiled.min(axis=(1, 3)).ravel(), tiled.max(axis=(1, 3)).ravel()

    def from_extrema(self, name, a, b):
        positive = np.maximum(b, 0.0)
        negative = np.maximum(-a, 0.0)
        if name == "block_abs":
            return float(np.max(self.upper_response @ np.maximum(positive, negative)))
        pos_upper = self.upper_response @ positive
        neg_upper = self.upper_response @ negative
        if name == "two_endpoint":
            pos_upper -= self.lower_response @ np.maximum(-b, 0.0)
            neg_upper -= self.lower_response @ np.maximum(a, 0.0)
        elif name != "block_sign":
            raise ValueError(name)
        return float(max(pos_upper.max(), neg_upper.max()))

    def bound(self, name, residual):
        if name == "analytic":
            return float(self.geometry.zmax * np.max(np.abs(residual)))
        if name == "sharp_scalar":
            return float(self.sharp_constant * np.max(np.abs(residual)))
        return self.from_extrema(name, *self.extrema(residual))

    def all_bounds(self, residual):
        """Post-hoc pairing; standalone estimator timing uses bound() instead."""
        amplitude = float(np.max(np.abs(residual)))
        a, b = self.extrema(residual)
        return {"analytic": self.geometry.zmax * amplitude, "sharp_scalar": self.sharp_constant * amplitude,
                **{name: self.from_extrema(name, a, b) for name in NAMES[2:]}}
