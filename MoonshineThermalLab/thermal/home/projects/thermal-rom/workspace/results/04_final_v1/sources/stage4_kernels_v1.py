"""Stage 4 reusable kernels; integrated FV equations; no test generation."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key] = '1'
import time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from thermal_solver import assemble, source_integrals
clock = time.perf_counter
TAU = 1e-3
CORRELATION = 1e-10
MAX_RANK = 32

def checked_h(h):
    h = np.asarray(h, dtype=float)
    if h.shape != (4,) or not np.all(np.isfinite(h)) or np.any(h < 0.2) or np.any(h > 5):
        raise ValueError('h must be finite and in [0.2,5]^4')
    return h

def finite(x):
    if not np.all(np.isfinite(x)):
        raise ValueError('nonfinite numerical value')
    return x

class Geometry:
    def __init__(self, n):
        started = clock()
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
            raise ValueError('positive integer n required')
        self.n = int(n)
        self.delta = 1.0/n
        N = n*n
        grid = np.arange(N).reshape(n,n)
        p = np.concatenate((grid[:,:-1].ravel(), grid[:-1,:].ravel()))
        q = np.concatenate((grid[:,1:].ravel(), grid[1:,:].ravel()))
        rows = np.concatenate((p,q,p,q,np.arange(N)))
        cols = np.concatenate((p,q,q,p,np.arange(N)))
        data = np.concatenate((np.ones(len(p)),np.ones(len(p)),-np.ones(len(p)),-np.ones(len(p)),np.zeros(N)))
        self.K = coo_matrix((data,(rows,cols)),shape=(N,N)).tocsr()
        self.K.sort_indices()
        self.diag_positions = np.array([self.K.indptr[i]+np.searchsorted(self.K.indices[self.K.indptr[i]:self.K.indptr[i+1]],i) for i in range(N)])
        self.ids = (grid[:,0],grid[:,-1],grid[0,:],grid[-1,:])
        self.b = source_integrals(n)
        self.geometry_seconds = clock()-started
        started = clock()
        x = (np.arange(n)+0.5)/n
        f = x*(1-x)
        self.z = (5+f[:,None]+f[None,:]).ravel()/(4*self.delta**2)
        self.zmax = float(self.z.max())
        self.barrier_seconds = clock()-started

    def beta(self,h):
        return self.delta/(self.delta/2+1/checked_h(h))

    def matrix(self,h):
        beta = self.beta(h)
        A = self.K.copy()
        for s,ids in enumerate(self.ids):
            A.data[self.diag_positions[ids]] += beta[s]
        return A

    def action(self,h,u):
        beta = self.beta(h)
        v = self.K @ u
        for s,ids in enumerate(self.ids):
            v[ids] += beta[s]*u[ids]
        return v

def full_solve(g,h,fast=True):
    t0 = clock()
    checked_h(h)
    if fast:
        A,b = g.matrix(h),g.b
    else:
        A,b,_ = assemble(g.n,h)
    t1 = clock()
    u = finite(spsolve(A,b))
    t2 = clock()
    return u, {'assembly_seconds':t1-t0,'solve_seconds':t2-t1,'service_seconds':t2-t0,'fom_calls':1}

class Reduced:
    def __init__(self,g,V):
        t0 = clock()
        self.g = g
        self.V = finite(np.array(V,dtype=float,copy=True))
        if self.V.ndim != 2 or self.V.shape[0] != g.n*g.n or not 0 < self.V.shape[1] <= min(MAX_RANK,g.n*g.n):
            raise ValueError('illegal basis dimensions')
        self.rebuild()
        self.initialization_seconds = clock()-t0
        self.rom_calls = 0
        self.fom_calls = 0
        self.updates = 0

    def rebuild(self):
        V = self.V
        self.Kr = V.T @ (self.g.K @ V)
        self.Dr = np.array([V[ids].T @ V[ids] for ids in self.g.ids])
        self.br = V.T @ self.g.b

    def predict(self,h,fast=True):
        t0 = clock()
        beta = self.g.beta(h)
        if fast:
            Ar = self.Kr.copy()
            for s in range(4):
                Ar += beta[s]*self.Dr[s]
            br = self.br
            t1 = clock()
            t2 = t1
        else:
            A,b,_ = assemble(self.g.n,h)
            t1 = clock()
            Ar = self.V.T @ (A @ self.V)
            br = self.V.T @ b
            t2 = clock()
        a = finite(np.linalg.solve(Ar,br))
        t3 = clock()
        u = finite(self.V @ a)
        t4 = clock()
        self.rom_calls += 1
        timing = {'assembly_seconds':t1-t0,'projection_seconds':t2-t1,'reduced_solve_seconds':t3-t2,'reconstruction_seconds':t4-t3,'service_seconds':t4-t0}
        return u,timing

    def augment(self,u):
        u = finite(np.asarray(u,dtype=float))
        if u.shape != (self.V.shape[0],):
            raise ValueError('wrong full solution shape')
        denom = float(np.linalg.norm(u))
        finite(denom)
        if denom == 0:
            return {'status':'zero_solution','relative_orthogonal_residual':None}
        w = u.copy()
        for _ in range(2):
            w -= self.V @ (self.V.T @ w)
        normw = float(np.linalg.norm(w))
        rel = float(normw/denom)
        finite(rel)
        if self.V.shape[1] >= min(MAX_RANK,self.V.shape[0]):
            status = 'rank_cap'
        elif rel <= CORRELATION:
            status = 'correlated'
        else:
            self.V = np.column_stack((self.V,w/normw))
            self.rebuild()
            self.updates += 1
            status = 'augmented'
        return {'status':status,'relative_orthogonal_residual':rel}

    def adaptive(self,h):
        t0 = clock()
        before = self.V.shape[1]
        pre,timing = self.predict(h,fast=True)
        td = clock()
        residual = finite(self.g.b-self.g.action(h,pre))
        eta = float(np.max(np.abs(residual))*self.g.zmax)
        finite(eta)
        timing['decision_residual_indicator_seconds'] = clock()-td
        trigger = eta > TAU
        update = {'status':'not_triggered','relative_orthogonal_residual':None}
        timing['fallback_seconds'] = 0.0
        timing['update_seconds'] = 0.0
        out = pre
        if trigger:
            self.fom_calls += 1
            out,ft = full_solve(self.g,h,fast=True)
            timing['fallback_seconds'] = ft['service_seconds']
            timing['fallback_assembly_seconds'] = ft['assembly_seconds']
            timing['fallback_solve_seconds'] = ft['solve_seconds']
            tu = clock()
            update = self.augment(out)
            timing['update_seconds'] = clock()-tu
        timing['service_seconds'] = clock()-t0
        info = {'eta':eta,'trigger':bool(trigger),'returned_fom':bool(trigger),'rank_before':before,'rank_after':self.V.shape[1],**update,'timing':timing}
        return out,pre,info

def diagnostics(g,h,u):
    t0 = clock()
    r = finite(g.b-g.action(h,u))
    linf = float(np.max(np.abs(r)))
    denom = float(np.linalg.norm(g.b))
    num = float(np.linalg.norm(r))
    relative = num/denom if denom else (0.0 if num == 0 else None)
    return {'residual_linf':linf,'relative_residual_l2':relative,'eta':linf*g.zmax,'seconds':clock()-t0}

def errors(u,ref):
    d = finite(u-ref)
    numerator,denominator = float(np.linalg.norm(d)),float(np.linalg.norm(ref))
    return {'hotspot':float(abs(np.max(u)-np.max(ref))),'field_linf':float(np.max(np.abs(d))),'relative_l2':numerator/denominator if denominator else (0.0 if numerator == 0 else None)}
