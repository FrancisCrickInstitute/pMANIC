//! Small dense linear algebra routines for variable projection and TRF.
//!
//! Matrices are stored row-major: element `(i, j)` of an `(m, n)` matrix is at
//! `i * n + j`. Dimensions here are small (`dim <= 6` for Gram systems,
//! `n <= 15` for Jacobian SVDs), so simple allocation-light routines are fast
//! and exact.

/// Solve `A X = B` in place using Gaussian elimination with partial pivoting.
///
/// `a` is `dim x dim` row-major, `b` is `dim x nrhs` row-major.
/// Returns `false` if a singular/non-finite pivot is encountered.
pub fn solve_linear_system(a: &mut [f64], b: &mut [f64], dim: usize, nrhs: usize) -> bool {
    for k in 0..dim {
        // Partial pivoting on column k.
        let mut pivot_row = k;
        let mut pivot_abs = a[k * dim + k].abs();
        for i in (k + 1)..dim {
            let v = a[i * dim + k].abs();
            if v > pivot_abs {
                pivot_abs = v;
                pivot_row = i;
            }
        }
        if !pivot_abs.is_finite() || pivot_abs == 0.0 {
            return false;
        }
        if pivot_row != k {
            for j in k..dim {
                a.swap(k * dim + j, pivot_row * dim + j);
            }
            for j in 0..nrhs {
                b.swap(k * nrhs + j, pivot_row * nrhs + j);
            }
        }
        let pivot = a[k * dim + k];
        for i in (k + 1)..dim {
            let factor = a[i * dim + k] / pivot;
            if factor == 0.0 {
                continue;
            }
            a[i * dim + k] = 0.0;
            for j in (k + 1)..dim {
                a[i * dim + j] -= factor * a[k * dim + j];
            }
            let row_i = i * nrhs;
            let row_k = k * nrhs;
            for j in 0..nrhs {
                b[row_i + j] -= factor * b[row_k + j];
            }
        }
    }

    // Back-substitution.
    for k in (0..dim).rev() {
        let diag = a[k * dim + k];
        if !diag.is_finite() || diag == 0.0 {
            return false;
        }
        let row_k = k * nrhs;
        for j in 0..nrhs {
            let mut sum = b[row_k + j];
            for col in (k + 1)..dim {
                sum -= a[k * dim + col] * b[col * nrhs + j];
            }
            b[row_k + j] = sum / diag;
        }
    }
    true
}

/// Thin SVD `A = U diag(s) V^T` for `m x n` row-major `A` with `m >= n`.
///
/// Uses Householder QR (`A = Q R`) followed by one-sided Jacobi SVD on the
/// tiny `n x n` upper-triangular factor `R`. Returns `(U, s, V)` where:
/// - `U` is `m x n` row-major with orthonormal columns,
/// - `s` is length `n` sorted in descending order (`s[0] >= ... >= s[n-1] >= 0`),
/// - `V` is `n x n` row-major (NOT transposed, matching `V = VT.T` in SciPy's TRF).
pub fn thin_svd(a: &[f64], m: usize, n: usize) -> Option<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    if n == 0 || m < n {
        return None;
    }

    // Step 1: Householder QR factorization of A (m x n).
    // Store working matrix column-major `qr_cols[col][row]` for cache-friendly inner loops.
    let mut qr = vec![0.0; m * n];
    for i in 0..m {
        for j in 0..n {
            qr[j * m + i] = a[i * n + j];
        }
    }
    let mut taus = vec![0.0; n];
    let mut r_mat = vec![0.0; n * n]; // row-major n x n

    for k in 0..n {
        let col = &mut qr[k * m..(k + 1) * m];
        let mut norm_sq = 0.0;
        for &v in &col[k..m] {
            norm_sq += v * v;
        }
        let norm = norm_sq.sqrt();
        if !norm.is_finite() {
            return None;
        }
        if norm == 0.0 {
            taus[k] = 0.0;
            r_mat[k * n + k] = 0.0;
            for j in (k + 1)..n {
                r_mat[k * n + j] = qr[j * m + k];
            }
            continue;
        }
        let x0 = col[k];
        let alpha = if x0 >= 0.0 { -norm } else { norm };
        let v0 = x0 - alpha;
        // Scale Householder vector v so v[0] = 1.
        let mut v_tail_sq = 0.0;
        for val in &mut col[(k + 1)..m] {
            *val /= v0;
            v_tail_sq += (*val) * (*val);
        }
        col[k] = 1.0;
        let tau = 2.0 / (1.0 + v_tail_sq);
        taus[k] = tau;
        r_mat[k * n + k] = alpha;

        // Apply H_k = I - tau v v^T to remaining columns j = k+1 .. n.
        let (left, right) = qr.split_at_mut((k + 1) * m);
        let v_col = &left[k * m..(k + 1) * m];
        for j in (k + 1)..n {
            let target = &mut right[(j - k - 1) * m..(j - k) * m];
            let mut dot = target[k];
            for i in (k + 1)..m {
                dot += v_col[i] * target[i];
            }
            let scale = tau * dot;
            target[k] -= scale;
            for i in (k + 1)..m {
                target[i] -= scale * v_col[i];
            }
            r_mat[k * n + j] = target[k];
        }
    }

    // Form thin Q (m x n) stored column-major `q_cols[col * m + row]`.
    let mut q_cols = vec![0.0; m * n];
    for j in 0..n {
        q_cols[j * m + j] = 1.0;
    }
    for k in (0..n).rev() {
        let tau = taus[k];
        if tau == 0.0 {
            continue;
        }
        let v_col = &qr[k * m..(k + 1) * m];
        for j in k..n {
            let qj = &mut q_cols[j * m..(j + 1) * m];
            let mut dot = qj[k];
            for i in (k + 1)..m {
                dot += v_col[i] * qj[i];
            }
            let scale = tau * dot;
            qj[k] -= scale;
            for i in (k + 1)..m {
                qj[i] -= scale * v_col[i];
            }
        }
    }

    // Step 2: One-sided Jacobi SVD on R (n x n).
    // Work with columns of W = R * V (initially R) and V (initially I).
    let mut w_cols = vec![0.0; n * n]; // col-major: col j is w_cols[j*n..(j+1)*n]
    for i in 0..n {
        for j in 0..n {
            w_cols[j * n + i] = r_mat[i * n + j];
        }
    }
    let mut v_cols = vec![0.0; n * n]; // col-major: col j is v_cols[j*n..(j+1)*n]
    for j in 0..n {
        v_cols[j * n + j] = 1.0;
    }

    let max_sweeps = 60;
    // Inner products of length n carry O(n * eps) roundoff, so a 1*eps
    // cutoff can spin forever on an already-orthogonalized pair.
    let tol = (n.max(4) as f64) * f64::EPSILON;
    let mut jacobi_converged = false;
    for _sweep in 0..max_sweeps {
        let mut converged = true;
        for p in 0..n {
            for q in (p + 1)..n {
                let mut a_pp = 0.0;
                let mut a_qq = 0.0;
                let mut a_pq = 0.0;
                let p_off = p * n;
                let q_off = q * n;
                for i in 0..n {
                    let wp = w_cols[p_off + i];
                    let wq = w_cols[q_off + i];
                    a_pp += wp * wp;
                    a_qq += wq * wq;
                    a_pq += wp * wq;
                }
                if a_pq.abs() <= tol * (a_pp * a_qq).sqrt() {
                    continue;
                }
                converged = false;
                let zeta = (a_qq - a_pp) / (2.0 * a_pq);
                let t = if zeta >= 0.0 {
                    1.0 / (zeta + (1.0 + zeta * zeta).sqrt())
                } else {
                    -1.0 / (-zeta + (1.0 + zeta * zeta).sqrt())
                };
                let c = 1.0 / (1.0 + t * t).sqrt();
                let s_rot = c * t;

                for i in 0..n {
                    let wp = w_cols[p_off + i];
                    let wq = w_cols[q_off + i];
                    w_cols[p_off + i] = c * wp - s_rot * wq;
                    w_cols[q_off + i] = s_rot * wp + c * wq;

                    let vp = v_cols[p_off + i];
                    let vq = v_cols[q_off + i];
                    v_cols[p_off + i] = c * vp - s_rot * vq;
                    v_cols[q_off + i] = s_rot * vp + c * vq;
                }
            }
        }
        if converged {
            jacobi_converged = true;
            break;
        }
    }
    if !jacobi_converged {
        return None;
    }

    // Extract singular values and normalize columns of W into U_R.
    let mut s_vals = vec![0.0; n];
    for j in 0..n {
        let mut norm_sq = 0.0;
        for i in 0..n {
            let val = w_cols[j * n + i];
            norm_sq += val * val;
        }
        let sigma = norm_sq.sqrt();
        if !sigma.is_finite() {
            return None;
        }
        s_vals[j] = sigma;
        if sigma > 0.0 {
            let inv = 1.0 / sigma;
            for i in 0..n {
                w_cols[j * n + i] *= inv;
            }
        }
    }

    // Sort singular values descending.
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&i, &j| {
        s_vals[j]
            .partial_cmp(&s_vals[i])
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let mut s_sorted = vec![0.0; n];
    let mut u_r_cols = vec![0.0; n * n];
    let mut v_row_major = vec![0.0; n * n];
    for (new_j, &old_j) in order.iter().enumerate() {
        s_sorted[new_j] = s_vals[old_j];
        for i in 0..n {
            u_r_cols[new_j * n + i] = w_cols[old_j * n + i];
            v_row_major[i * n + new_j] = v_cols[old_j * n + i];
        }
    }

    // Zero singular values leave their U_R column zero; solve_lsq_trust_region
    // multiplies uf[j] by s[j] = 0 so null-space U columns never enter the step.
    // Multiply U = Q * U_R (m x n, returned row-major).
    let mut u_row_major = vec![0.0; m * n];
    for j in 0..n {
        let ur_col = &u_r_cols[j * n..(j + 1) * n];
        for k in 0..n {
            let coef = ur_col[k];
            if coef == 0.0 {
                continue;
            }
            let q_col = &q_cols[k * m..(k + 1) * m];
            for i in 0..m {
                u_row_major[i * n + j] += q_col[i] * coef;
            }
        }
    }

    Some((u_row_major, s_sorted, v_row_major))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn solve_3x3_system() {
        let mut a = vec![2.0, 1.0, -1.0, -3.0, -1.0, 2.0, -2.0, 1.0, 2.0];
        let mut b = vec![8.0, -11.0, -3.0];
        assert!(solve_linear_system(&mut a, &mut b, 3, 1));
        assert!((b[0] - 2.0).abs() < 1e-12);
        assert!((b[1] - 3.0).abs() < 1e-12);
        assert!((b[2] - (-1.0)).abs() < 1e-12);
    }

    #[test]
    fn thin_svd_reconstructs_rectangular_and_rank_deficient() {
        let m = 6;
        let n = 3;
        let a = vec![
            1.0, 2.0, 3.0,
            4.0, 5.0, 6.0,
            7.0, 8.0, 10.0,
            2.0, 1.0, 0.5,
            -1.0, 3.0, 2.0,
            0.5, -2.0, 4.0,
        ];
        let (u, s, v) = thin_svd(&a, m, n).expect("svd");
        assert!(s[0] >= s[1] && s[1] >= s[2] && s[2] > 0.0);
        // Reconstruct U diag(s) V^T and compare with A.
        for i in 0..m {
            for j in 0..n {
                let mut acc = 0.0;
                for k in 0..n {
                    acc += u[i * n + k] * s[k] * v[j * n + k];
                }
                assert!((acc - a[i * n + j]).abs() < 1e-12);
            }
        }
        // Rank-deficient matrix (col 2 = col 0 + col 1).
        let rank_def = vec![
            1.0, 2.0, 3.0,
            4.0, 5.0, 9.0,
            7.0, 8.0, 15.0,
            2.0, 1.0, 3.0,
        ];
        let (u2, s2, v2) = thin_svd(&rank_def, 4, 3).expect("rank-def svd");
        assert!(s2[2] < 1e-12);
        for i in 0..4 {
            for j in 0..3 {
                let mut acc = 0.0;
                for k in 0..3 {
                    acc += u2[i * 3 + k] * s2[k] * v2[j * 3 + k];
                }
                assert!((acc - rank_def[i * 3 + j]).abs() < 1e-12);
            }
        }
    }

    #[test]
    fn thin_svd_handles_zero_leading_and_middle_columns() {
        // Zero leading column: [[0, 1], [0, 0], [0, 0]]
        let a = vec![0.0, 1.0, 0.0, 0.0, 0.0, 0.0];
        let (u, s, v) = thin_svd(&a, 3, 2).expect("zero leading col");
        assert!((s[0] - 1.0).abs() < 1e-12);
        assert!(s[1].abs() < 1e-12);
        for i in 0..3 {
            for j in 0..2 {
                let acc: f64 = (0..2).map(|k| u[i * 2 + k] * s[k] * v[j * 2 + k]).sum();
                assert!((acc - a[i * 2 + j]).abs() < 1e-12);
            }
        }

        // Zero middle column in 4x3 matrix.
        let b = vec![
            1.0, 0.0, 2.0,
            0.0, 0.0, 3.0,
            4.0, 0.0, -1.0,
            2.0, 0.0, 5.0,
        ];
        let (u2, s2, v2) = thin_svd(&b, 4, 3).expect("zero middle col");
        assert!(s2[2].abs() < 1e-12);
        for i in 0..4 {
            for j in 0..3 {
                let acc: f64 = (0..3).map(|k| u2[i * 3 + k] * s2[k] * v2[j * 3 + k]).sum();
                assert!((acc - b[i * 3 + j]).abs() < 1e-12);
            }
        }
    }
}
