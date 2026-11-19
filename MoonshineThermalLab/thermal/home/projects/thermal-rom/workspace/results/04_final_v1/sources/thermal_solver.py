"""Conservative cell-centred FV; integrated balances, k=1, unit square.
Ordering p=j*n+i; sides left,right,bottom,top. No dependency installation."""
import time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve


def source_integrals(n):
    """Exact rectangle/cell overlap integration, up to floating-point roundoff."""
    edges = np.arange(n + 1, dtype=float) / n
    b = np.zeros((n, n), dtype=float)
    for lo, hi, strength in ((0.2, 0.4, 1.0), (0.6, 0.8, 2.0)):
        overlap = np.maximum(0.0, np.minimum(edges[1:], hi) - np.maximum(edges[:-1], lo))
        b += strength * np.outer(overlap, overlap)
    return b.ravel()


def assemble(n=24, h=(1.0, 1.0, 1.0, 1.0), source='fixed', ambient=0.0):
    """Return CSR A, integrated b, and boundary metadata.
    source='fixed' uses the project heat rectangles; 'zero' is a validation case.
    ambient is a common boundary ambient temperature, normally zero.
    """
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError('n must be a positive integer')
    h = np.asarray(h, dtype=float)
    if h.shape != (4,) or not np.all(np.isfinite(h)) or np.any(h <= 0):
        raise ValueError('four finite positive Robin coefficients required')
    if not np.isfinite(ambient):
        raise ValueError('finite ambient required')
    delta = 1.0 / n
    g = delta / (delta / 2.0 + 1.0 / h)
    rows, cols, data = [], [], []
    def add(i, j, value):
        rows.append(i); cols.append(j); data.append(value)
    for j in range(n):
        for i in range(n):
            p = j * n + i
            neighbors = []
            if i + 1 < n:
                neighbors.append(p + 1)
            if j + 1 < n:
                neighbors.append(p + n)
            for q in neighbors:
                add(p, p, 1.0); add(q, q, 1.0)
                add(p, q, -1.0); add(q, p, -1.0)
    ids = (np.arange(n) * n, np.arange(n) * n + n - 1,
           np.arange(n), (n - 1) * n + np.arange(n))
    boundary_diag = np.zeros(n * n)
    for side in range(4):
        for p in ids[side]:
            add(int(p), int(p), float(g[side]))
            boundary_diag[p] += g[side]
    A = coo_matrix((data, (rows, cols)), shape=(n*n, n*n)).tocsr()
    if source == 'fixed':
        heat = source_integrals(n)
    elif source == 'zero':
        heat = np.zeros(n * n)
    else:
        raise ValueError('source must be fixed or zero')
    b = heat + boundary_diag * float(ambient)
    meta = {'n': n, 'h': h, 'delta': delta, 'g': g, 'boundary_ids': ids,
            'source_integrals': heat, 'ambient': float(ambient)}
    return A, b, meta


def solve(n=24, h=(1.0, 1.0, 1.0, 1.0), source='fixed', ambient=0.0):
    start = time.perf_counter()
    A, b, meta = assemble(n, h, source, ambient)
    assembled = time.perf_counter()
    temperature = spsolve(A, b)
    finished = time.perf_counter()
    timing = {'assembly_seconds': assembled-start, 'linear_solve_seconds': finished-assembled,
              'assembly_and_solve_seconds': finished-start, 'full_solve_count': 1}
    return temperature, A, b, meta, timing


def boundary_heat(temperature, meta):
    return np.array([meta['g'][s] * np.sum(temperature[meta['boundary_ids'][s]] - meta['ambient'])
                     for s in range(4)])
