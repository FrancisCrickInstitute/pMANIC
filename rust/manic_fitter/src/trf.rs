//! Faithful Rust port of SciPy's bounded Trust-Region Reflective (`trf_bounds`)
//! least-squares solver with `x_scale = "jac"`, `tr_solver = "exact"`, and
//! default tolerances (`ftol = xtol = gtol = 1e-8`).

use crate::linalg::thin_svd;
use crate::shapes::VarProProblem;

const FTOL: f64 = 1e-8;
const XTOL: f64 = 1e-8;
const GTOL: f64 = 1e-8;
const EPS: f64 = f64::EPSILON;

pub struct TrfResult {
    pub x: Vec<f64>,
    pub status: i32,
}

#[inline]
fn dot(a: &[f64], b: &[f64]) -> f64 {
    let mut s = 0.0;
    for i in 0..a.len() {
        s += a[i] * b[i];
    }
    s
}

#[inline]
fn norm2(a: &[f64]) -> f64 {
    dot(a, a).sqrt()
}

/// IEEE-754 `nextafter(x, y)` compatible with Rust 1.76.
fn nextafter(x: f64, y: f64) -> f64 {
    if x.is_nan() || y.is_nan() {
        return f64::NAN;
    }
    if x == y {
        return y;
    }
    if x == 0.0 {
        return if y > 0.0 {
            f64::from_bits(1)
        } else {
            f64::from_bits(1 | (1u64 << 63))
        };
    }
    let bits = x.to_bits();
    let inc = (x > 0.0) == (y > x);
    let next_bits = if inc { bits + 1 } else { bits - 1 };
    f64::from_bits(next_bits)
}

fn in_bounds(x: &[f64], lb: &[f64], ub: &[f64]) -> bool {
    for i in 0..x.len() {
        if !(x[i] >= lb[i] && x[i] <= ub[i]) {
            return false;
        }
    }
    true
}

fn find_active_constraints(x: &[f64], lb: &[f64], ub: &[f64], rtol: f64) -> Vec<i8> {
    let n = x.len();
    let mut active = vec![0i8; n];
    if rtol == 0.0 {
        for i in 0..n {
            if x[i] <= lb[i] {
                active[i] = -1;
            } else if x[i] >= ub[i] {
                active[i] = 1;
            }
        }
        return active;
    }
    for i in 0..n {
        let lower_dist = x[i] - lb[i];
        let upper_dist = ub[i] - x[i];
        let lower_thresh = rtol * lb[i].abs().max(1.0);
        let upper_thresh = rtol * ub[i].abs().max(1.0);
        if lb[i].is_finite() && lower_dist <= upper_dist.min(lower_thresh) {
            active[i] = -1;
        } else if ub[i].is_finite() && upper_dist <= lower_dist.min(upper_thresh) {
            active[i] = 1;
        }
    }
    active
}

fn make_strictly_feasible(x: &[f64], lb: &[f64], ub: &[f64], rstep: f64) -> Vec<f64> {
    let n = x.len();
    let mut x_new = x.to_vec();
    let active = find_active_constraints(x, lb, ub, rstep);
    for i in 0..n {
        if active[i] == -1 {
            x_new[i] = if rstep == 0.0 {
                nextafter(lb[i], ub[i])
            } else {
                lb[i] + rstep * lb[i].abs().max(1.0)
            };
        } else if active[i] == 1 {
            x_new[i] = if rstep == 0.0 {
                nextafter(ub[i], lb[i])
            } else {
                ub[i] - rstep * ub[i].abs().max(1.0)
            };
        }
        if x_new[i] < lb[i] || x_new[i] > ub[i] {
            x_new[i] = 0.5 * (lb[i] + ub[i]);
        }
    }
    x_new
}

fn cl_scaling_vector(x: &[f64], g: &[f64], lb: &[f64], ub: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let n = x.len();
    let mut v = vec![1.0; n];
    let mut dv = vec![0.0; n];
    for i in 0..n {
        if g[i] < 0.0 && ub[i].is_finite() {
            v[i] = ub[i] - x[i];
            dv[i] = -1.0;
        } else if g[i] > 0.0 && lb[i].is_finite() {
            v[i] = x[i] - lb[i];
            dv[i] = 1.0;
        }
    }
    (v, dv)
}

fn compute_grad(j_mat: &[f64], f: &[f64], m: usize, n: usize) -> Vec<f64> {
    let mut g = vec![0.0; n];
    for i in 0..m {
        let fi = f[i];
        let row = &j_mat[i * n..(i + 1) * n];
        for c in 0..n {
            g[c] += row[c] * fi;
        }
    }
    g
}

fn compute_jac_scale(
    j_mat: &[f64],
    m: usize,
    n: usize,
    scale_inv_old: Option<&[f64]>,
) -> (Vec<f64>, Vec<f64>) {
    let mut scale_inv = vec![0.0; n];
    for i in 0..m {
        let row = &j_mat[i * n..(i + 1) * n];
        for c in 0..n {
            scale_inv[c] += row[c] * row[c];
        }
    }
    for c in 0..n {
        scale_inv[c] = scale_inv[c].sqrt();
        match scale_inv_old {
            None => {
                if scale_inv[c] == 0.0 {
                    scale_inv[c] = 1.0;
                }
            }
            Some(old) => {
                if old[c] > scale_inv[c] {
                    scale_inv[c] = old[c];
                }
            }
        }
    }
    let scale = scale_inv.iter().map(|&v| 1.0 / v).collect();
    (scale, scale_inv)
}

fn matvec(j_mat: &[f64], s: &[f64], m: usize, n: usize) -> Vec<f64> {
    let mut out = vec![0.0; m];
    for i in 0..m {
        let row = &j_mat[i * n..(i + 1) * n];
        let mut acc = 0.0;
        for c in 0..n {
            acc += row[c] * s[c];
        }
        out[i] = acc;
    }
    out
}

fn evaluate_quadratic(j_mat: &[f64], g: &[f64], s: &[f64], diag: &[f64], m: usize, n: usize) -> f64 {
    let js = matvec(j_mat, s, m, n);
    let mut q = dot(&js, &js);
    for i in 0..n {
        q += s[i] * diag[i] * s[i];
    }
    0.5 * q + dot(s, g)
}

fn build_quadratic_1d(
    j_mat: &[f64],
    g: &[f64],
    s: &[f64],
    diag: &[f64],
    s0: Option<&[f64]>,
    m: usize,
    n: usize,
) -> (f64, f64, f64) {
    let v = matvec(j_mat, s, m, n);
    let mut a = dot(&v, &v);
    for i in 0..n {
        a += s[i] * diag[i] * s[i];
    }
    a *= 0.5;
    let mut b = dot(g, s);
    let mut c = 0.0;
    if let Some(s0_vec) = s0 {
        let u = matvec(j_mat, s0_vec, m, n);
        b += dot(&u, &v);
        c = 0.5 * dot(&u, &u) + dot(g, s0_vec);
        for i in 0..n {
            b += s0_vec[i] * diag[i] * s[i];
            c += 0.5 * s0_vec[i] * diag[i] * s0_vec[i];
        }
    }
    (a, b, c)
}

fn minimize_quadratic_1d(a: f64, b: f64, lb: f64, ub: f64, c: f64) -> (f64, f64) {
    let eval = |t: f64| t * (a * t + b) + c;
    let mut best_t = lb;
    let mut best_y = eval(lb);
    let y_ub = eval(ub);
    if y_ub < best_y {
        best_t = ub;
        best_y = y_ub;
    }
    if a != 0.0 {
        let ext = -0.5 * b / a;
        if ext > lb && ext < ub {
            let y_ext = eval(ext);
            if y_ext < best_y {
                best_t = ext;
                best_y = y_ext;
            }
        }
    }
    (best_t, best_y)
}

fn step_size_to_bound(x: &[f64], s: &[f64], lb: &[f64], ub: &[f64]) -> (f64, Vec<i8>) {
    let n = x.len();
    let mut steps = vec![f64::INFINITY; n];
    let mut min_step = f64::INFINITY;
    for i in 0..n {
        if s[i] != 0.0 {
            let t1 = (lb[i] - x[i]) / s[i];
            let t2 = (ub[i] - x[i]) / s[i];
            let st = t1.max(t2);
            steps[i] = st;
            if st < min_step {
                min_step = st;
            }
        }
    }
    let mut hits = vec![0i8; n];
    for i in 0..n {
        if steps[i] == min_step {
            hits[i] = if s[i] > 0.0 {
                1
            } else if s[i] < 0.0 {
                -1
            } else {
                0
            };
        }
    }
    (min_step, hits)
}

fn intersect_trust_region(x: &[f64], s: &[f64], delta: f64) -> Option<(f64, f64)> {
    let a = dot(s, s);
    if a == 0.0 {
        return None;
    }
    let b = dot(x, s);
    let c = dot(x, x) - delta * delta;
    if c > 0.0 {
        return None;
    }
    let d = (b * b - a * c).sqrt();
    let q = -(b + d.copysign(b));
    let t1 = q / a;
    let t2 = c / q;
    if t1 < t2 {
        Some((t1, t2))
    } else {
        Some((t2, t1))
    }
}

fn solve_lsq_trust_region(
    n: usize,
    m: usize,
    uf: &[f64],
    s: &[f64],
    v: &[f64], // n x n row-major
    delta: f64,
    initial_alpha: f64,
) -> (Vec<f64>, f64) {
    let rtol = 0.01;
    let max_iter = 10;

    let suf: Vec<f64> = (0..n).map(|i| s[i] * uf[i]).collect();

    let full_rank = if m >= n {
        let threshold = EPS * (m as f64) * s[0];
        s[n - 1] > threshold
    } else {
        false
    };

    if full_rank {
        let mut coeffs = vec![0.0; n];
        for i in 0..n {
            coeffs[i] = -uf[i] / s[i];
        }
        let p = matvec(v, &coeffs, n, n);
        if norm2(&p) <= delta {
            return (p, 0.0);
        }
    }

    let phi_and_deriv = |alpha: f64| -> (f64, f64) {
        let mut sum_sq = 0.0;
        let mut sum_d3 = 0.0;
        for i in 0..n {
            let denom = s[i] * s[i] + alpha;
            let q = suf[i] / denom;
            sum_sq += q * q;
            sum_d3 += (suf[i] * suf[i]) / (denom * denom * denom);
        }
        let p_norm = sum_sq.sqrt();
        let phi = p_norm - delta;
        let phi_prime = -sum_d3 / p_norm;
        (phi, phi_prime)
    };

    let mut alpha_upper = norm2(&suf) / delta;
    let mut alpha_lower = if full_rank {
        let (phi, phi_prime) = phi_and_deriv(0.0);
        -phi / phi_prime
    } else {
        0.0
    };

    let mut alpha = if !full_rank && initial_alpha == 0.0 {
        (0.001 * alpha_upper).max((alpha_lower * alpha_upper).sqrt())
    } else {
        initial_alpha
    };

    for _ in 0..max_iter {
        if alpha < alpha_lower || alpha > alpha_upper {
            alpha = (0.001 * alpha_upper).max((alpha_lower * alpha_upper).sqrt());
        }
        let (phi, phi_prime) = phi_and_deriv(alpha);
        if phi < 0.0 {
            alpha_upper = alpha;
        }
        let ratio = phi / phi_prime;
        let cand_lower = alpha - ratio;
        if cand_lower > alpha_lower {
            alpha_lower = cand_lower;
        }
        alpha -= (phi + delta) * ratio / delta;
        if phi.abs() < rtol * delta {
            break;
        }
    }

    let mut coeffs = vec![0.0; n];
    for i in 0..n {
        coeffs[i] = -suf[i] / (s[i] * s[i] + alpha);
    }
    let mut p = matvec(v, &coeffs, n, n);
    let pn = norm2(&p);
    // Avoid 0/0 if suf is identically zero at a stationary point.
    if pn > 0.0 {
        let scale = delta / pn;
        for val in &mut p {
            *val *= scale;
        }
    }
    (p, alpha)
}

#[allow(clippy::too_many_arguments)]
fn select_step(
    x: &[f64],
    j_h: &[f64],
    diag_h: &[f64],
    g_h: &[f64],
    mut p: Vec<f64>,
    mut p_h: Vec<f64>,
    d: &[f64],
    delta: f64,
    lb: &[f64],
    ub: &[f64],
    theta: f64,
    m: usize,
    n: usize,
) -> Option<(Vec<f64>, Vec<f64>, f64)> {
    let x_plus_p: Vec<f64> = (0..n).map(|i| x[i] + p[i]).collect();
    if in_bounds(&x_plus_p, lb, ub) {
        let p_value = evaluate_quadratic(j_h, g_h, &p_h, diag_h, m, n);
        return Some((p, p_h, -p_value));
    }

    let (p_stride, hits) = step_size_to_bound(x, &p, lb, ub);

    let mut r_h = p_h.clone();
    for i in 0..n {
        if hits[i] != 0 {
            r_h[i] = -r_h[i];
        }
    }
    let mut r: Vec<f64> = (0..n).map(|i| d[i] * r_h[i]).collect();

    for i in 0..n {
        p[i] *= p_stride;
        p_h[i] *= p_stride;
    }
    let x_on_bound: Vec<f64> = (0..n).map(|i| x[i] + p[i]).collect();

    // Match SciPy: intersect_trust_region failure aborts the candidate fit.
    let (_, to_tr) = intersect_trust_region(&p_h, &r_h, delta)?;
    let (to_bound, _) = step_size_to_bound(&x_on_bound, &r, lb, ub);

    let r_stride = to_bound.min(to_tr);
    let (r_stride_l, r_stride_u) = if r_stride > 0.0 {
        let l = (1.0 - theta) * p_stride / r_stride;
        let u = if r_stride == to_bound {
            theta * to_bound
        } else {
            to_tr
        };
        (l, u)
    } else {
        (0.0, -1.0)
    };

    let r_value = if r_stride_l <= r_stride_u {
        let (a, b, c) = build_quadratic_1d(j_h, g_h, &r_h, diag_h, Some(&p_h), m, n);
        let (stride, val) = minimize_quadratic_1d(a, b, r_stride_l, r_stride_u, c);
        for i in 0..n {
            r_h[i] = r_h[i] * stride + p_h[i];
            r[i] = r_h[i] * d[i];
        }
        val
    } else {
        f64::INFINITY
    };

    for i in 0..n {
        p[i] *= theta;
        p_h[i] *= theta;
    }
    let p_value = evaluate_quadratic(j_h, g_h, &p_h, diag_h, m, n);

    let mut ag_h: Vec<f64> = g_h.iter().map(|&v| -v).collect();
    let mut ag: Vec<f64> = (0..n).map(|i| d[i] * ag_h[i]).collect();

    let ag_h_norm = norm2(&ag_h);
    let to_tr_ag = delta / ag_h_norm;
    let (to_bound_ag, _) = step_size_to_bound(x, &ag, lb, ub);
    let ag_stride_ub = if to_bound_ag < to_tr_ag {
        theta * to_bound_ag
    } else {
        to_tr_ag
    };

    let (a_ag, b_ag, _) = build_quadratic_1d(j_h, g_h, &ag_h, diag_h, None, m, n);
    let (ag_stride, ag_value) = minimize_quadratic_1d(a_ag, b_ag, 0.0, ag_stride_ub, 0.0);
    for i in 0..n {
        ag_h[i] *= ag_stride;
        ag[i] *= ag_stride;
    }

    if p_value < r_value && p_value < ag_value {
        Some((p, p_h, -p_value))
    } else if r_value < p_value && r_value < ag_value {
        Some((r, r_h, -r_value))
    } else {
        Some((ag, ag_h, -ag_value))
    }
}

fn update_tr_radius(
    mut delta: f64,
    actual_reduction: f64,
    predicted_reduction: f64,
    step_norm: f64,
    bound_hit: bool,
) -> (f64, f64) {
    let ratio = if predicted_reduction > 0.0 {
        actual_reduction / predicted_reduction
    } else if predicted_reduction == 0.0 && actual_reduction == 0.0 {
        1.0
    } else {
        0.0
    };

    if ratio < 0.25 {
        delta = 0.25 * step_norm;
    } else if ratio > 0.75 && bound_hit {
        delta *= 2.0;
    }
    (delta, ratio)
}

fn check_termination(
    df: f64,
    cost: f64,
    dx_norm: f64,
    x_norm: f64,
    ratio: f64,
) -> Option<i32> {
    let ftol_ok = df < FTOL * cost && ratio > 0.25;
    let xtol_ok = dx_norm < XTOL * (XTOL + x_norm);
    match (ftol_ok, xtol_ok) {
        (true, true) => Some(4),
        (true, false) => Some(2),
        (false, true) => Some(3),
        (false, false) => None,
    }
}

/// Run bounded Trust-Region Reflective optimization on `prob`.
pub fn solve_trf_bounds(
    prob: &mut VarProProblem<'_>,
    initial: &[f64],
    lb: &[f64],
    ub: &[f64],
    max_nfev: usize,
) -> Option<TrfResult> {
    let n = prob.n_params();
    let m = prob.n_residuals();
    if initial.len() != n || lb.len() != n || ub.len() != n || m == 0 || n == 0 || max_nfev == 0 {
        return None;
    }
    for i in 0..n {
        if !(lb[i] < ub[i]) || !initial[i].is_finite() {
            return None;
        }
    }
    if !in_bounds(initial, lb, ub) {
        return None;
    }

    let mut x = make_strictly_feasible(initial, lb, ub, 1e-10);
    let mut f = prob.residual(&x)?;
    if !f.iter().all(|v| v.is_finite()) {
        return None;
    }
    let mut nfev = 1usize;

    let mut j_mat = prob.jacobian(&x)?;
    if !j_mat.iter().all(|v| v.is_finite()) {
        return None;
    }

    let mut cost = 0.5 * dot(&f, &f);
    let mut g = compute_grad(&j_mat, &f, m, n);
    let (mut scale, mut scale_inv) = compute_jac_scale(&j_mat, m, n, None);

    let (mut v0, dv0) = cl_scaling_vector(&x, &g, lb, ub);
    for i in 0..n {
        if dv0[i] != 0.0 {
            v0[i] *= scale_inv[i];
        }
    }
    let mut delta_sq = 0.0;
    for i in 0..n {
        let term = x[i] * scale_inv[i] / v0[i].sqrt();
        delta_sq += term * term;
    }
    let mut delta = delta_sq.sqrt();
    if delta == 0.0 || !delta.is_finite() {
        delta = 1.0;
    }

    let mut f_augmented = vec![0.0; m + n];
    let mut j_augmented = vec![0.0; (m + n) * n];
    let mut alpha = 0.0f64;
    let mut termination_status: Option<i32> = None;

    loop {
        let (mut v, dv) = cl_scaling_vector(&x, &g, lb, ub);

        let mut g_norm = 0.0f64;
        for i in 0..n {
            let val = (g[i] * v[i]).abs();
            if val > g_norm {
                g_norm = val;
            }
        }
        if g_norm < GTOL {
            termination_status = Some(1);
        }
        if termination_status.is_some() || nfev == max_nfev {
            break;
        }

        for i in 0..n {
            if dv[i] != 0.0 {
                v[i] *= scale_inv[i];
            }
        }
        let d: Vec<f64> = (0..n).map(|i| v[i].sqrt() * scale[i]).collect();
        let diag_h: Vec<f64> = (0..n).map(|i| g[i] * dv[i] * scale[i]).collect();
        let g_h: Vec<f64> = (0..n).map(|i| d[i] * g[i]).collect();

        f_augmented[..m].copy_from_slice(&f);
        for val in &mut f_augmented[m..] {
            *val = 0.0;
        }
        for i in 0..m {
            let src = &j_mat[i * n..(i + 1) * n];
            let dst = &mut j_augmented[i * n..(i + 1) * n];
            for c in 0..n {
                dst[c] = src[c] * d[c];
            }
        }
        for r in 0..n {
            let dst = &mut j_augmented[(m + r) * n..(m + r + 1) * n];
            for val in dst.iter_mut() {
                *val = 0.0;
            }
            dst[r] = diag_h[r].sqrt();
        }

        let (u_mat, s_vals, v_mat) = thin_svd(&j_augmented, m + n, n)?;
        // uf = U^T f_augmented (length n; f_augmented[m..] is zero so only sum 0..m).
        let mut uf = vec![0.0; n];
        for i in 0..m {
            let fi = f_augmented[i];
            let u_row = &u_mat[i * n..(i + 1) * n];
            for c in 0..n {
                uf[c] += u_row[c] * fi;
            }
        }

        let theta = 0.995f64.max(1.0 - g_norm);
        let j_h = &j_augmented[..m * n];

        let mut actual_reduction = -1.0f64;
        let mut x_new = Vec::new();
        let mut f_new = Vec::new();
        let mut cost_new = cost;

        while actual_reduction <= 0.0 && nfev < max_nfev {
            let (p_h, new_alpha) = solve_lsq_trust_region(n, m, &uf, &s_vals, &v_mat, delta, alpha);
            alpha = new_alpha;
            let p: Vec<f64> = (0..n).map(|i| d[i] * p_h[i]).collect();

            let (step, step_h, predicted_reduction) = select_step(
                &x, j_h, &diag_h, &g_h, p, p_h, &d, delta, lb, ub, theta, m, n,
            )?;

            let x_trial: Vec<f64> = (0..n).map(|i| x[i] + step[i]).collect();
            x_new = make_strictly_feasible(&x_trial, lb, ub, 0.0);
            let step_h_norm = norm2(&step_h);

            // Match SciPy: a singular linear solve aborts the candidate fit
            // (LinAlgError -> None), whereas non-finite residuals shrink Delta.
            let fv = prob.residual(&x_new)?;
            nfev += 1;
            if !fv.iter().all(|v| v.is_finite()) {
                delta = 0.25 * step_h_norm;
                continue;
            }
            f_new = fv;

            cost_new = 0.5 * dot(&f_new, &f_new);
            actual_reduction = cost - cost_new;
            let (delta_new, ratio) = update_tr_radius(
                delta,
                actual_reduction,
                predicted_reduction,
                step_h_norm,
                step_h_norm > 0.95 * delta,
            );

            let step_norm = norm2(&step);
            termination_status =
                check_termination(actual_reduction, cost, step_norm, norm2(&x), ratio);
            if termination_status.is_some() {
                break;
            }

            // Guard against 0/0 if a zero-norm step collapsed Delta_new to 0.
            if delta_new > 0.0 {
                alpha *= delta / delta_new;
            }
            delta = delta_new;
        }

        if actual_reduction > 0.0 {
            x = x_new;
            f = f_new;
            cost = cost_new;
            j_mat = prob.jacobian(&x)?;
            if !j_mat.iter().all(|v| v.is_finite()) {
                return None;
            }
            g = compute_grad(&j_mat, &f, m, n);
            let (new_scale, new_scale_inv) = compute_jac_scale(&j_mat, m, n, Some(&scale_inv));
            scale = new_scale;
            scale_inv = new_scale_inv;
        }
    }

    let status = termination_status.unwrap_or(0);
    if !x.iter().all(|v| v.is_finite()) {
        return None;
    }
    Some(TrfResult { x, status })
}
