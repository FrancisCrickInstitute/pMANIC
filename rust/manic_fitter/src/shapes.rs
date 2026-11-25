//! Chromatographic peak shapes and Golub-Pereyra variable-projection residual
//! and Jacobian matching `chromatographic_peak_deconvolution.py`.

use crate::erfc::{erfc, erfcx};
use crate::linalg::solve_linear_system;

const RIDGE: f64 = 1e-12;
const SQRT_2: f64 = std::f64::consts::SQRT_2;
const TWO_OVER_SQRT_PI: f64 = std::f64::consts::FRAC_2_SQRT_PI;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ShapeModel {
    Gaussian = 0,
    BiGaussian = 1,
    Emg = 2,
}

impl ShapeModel {
    pub fn from_code(code: i32) -> Option<Self> {
        match code {
            0 => Some(Self::Gaussian),
            1 => Some(Self::BiGaussian),
            2 => Some(Self::Emg),
            _ => None,
        }
    }

    #[inline]
    pub fn param_count(self) -> usize {
        match self {
            Self::Gaussian => 2,
            Self::BiGaussian | Self::Emg => 3,
        }
    }
}

/// Cached intermediate values from the most recent residual evaluation so the
/// immediately following Jacobian evaluation avoids recomputing shapes and
/// normal equations.
pub struct CachedEval {
    pub x: Vec<f64>,
    pub raw: Vec<f64>,    // K x points
    pub shapes: Vec<f64>, // K x points
    pub design: Vec<f64>, // points x (1+K)
    pub gram: Vec<f64>,   // (1+K) x (1+K)
}

pub struct VarProProblem<'a> {
    pub x_rel: &'a [f64],
    pub y: &'a [f64],             // channels x points, row-major
    pub channel_scale: &'a [f64], // length channels
    pub channels: usize,
    pub points: usize,
    pub component_count: usize,
    pub shape_model: ShapeModel,
    pub last_eval: Option<CachedEval>,
}

impl<'a> VarProProblem<'a> {
    pub fn new(
        x_rel: &'a [f64],
        y: &'a [f64],
        channel_scale: &'a [f64],
        channels: usize,
        points: usize,
        component_count: usize,
        shape_model: ShapeModel,
    ) -> Self {
        Self {
            x_rel,
            y,
            channel_scale,
            channels,
            points,
            component_count,
            shape_model,
            last_eval: None,
        }
    }

    #[inline]
    pub fn n_params(&self) -> usize {
        self.component_count * self.shape_model.param_count()
    }

    #[inline]
    pub fn n_residuals(&self) -> usize {
        self.channels * self.points
    }

    fn compute_raw_and_shapes(&self, values: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let k_cnt = self.component_count;
        let p_cnt = self.shape_model.param_count();
        let pts = self.points;
        let eps = f64::EPSILON;

        let mut raw = vec![0.0; k_cnt * pts];
        let mut shapes = vec![0.0; k_cnt * pts];

        for k in 0..k_cnt {
            let base = k * p_cnt;
            let center = values[base];
            let row_off = k * pts;
            let mut max_val = f64::NEG_INFINITY;

            match self.shape_model {
                ShapeModel::Gaussian => {
                    let sigma = values[base + 1];
                    let inv_sigma = 1.0 / sigma;
                    for i in 0..pts {
                        let u = (self.x_rel[i] - center) * inv_sigma;
                        let val = (-0.5 * u * u).exp();
                        raw[row_off + i] = val;
                        if val > max_val {
                            max_val = val;
                        }
                    }
                }
                ShapeModel::BiGaussian => {
                    let s_left = values[base + 1];
                    let s_right = values[base + 2];
                    let inv_left = 1.0 / s_left;
                    let inv_right = 1.0 / s_right;
                    for i in 0..pts {
                        let dx = self.x_rel[i] - center;
                        let u = dx * if dx < 0.0 { inv_left } else { inv_right };
                        let val = (-0.5 * u * u).exp();
                        raw[row_off + i] = val;
                        if val > max_val {
                            max_val = val;
                        }
                    }
                }
                ShapeModel::Emg => {
                    let sigma = values[base + 1].max(eps);
                    let tau = values[base + 2].max(eps);
                    let ratio = sigma / tau;
                    let half_ratio_sq = 0.5 * ratio * ratio;
                    let inv_sigma = 1.0 / sigma;
                    for i in 0..pts {
                        let u = (self.x_rel[i] - center) * inv_sigma;
                        let z = (ratio - u) / SQRT_2;
                        let val = if z < 0.0 {
                            (half_ratio_sq - u * ratio).min(0.0).exp() * erfc(z)
                        } else {
                            (-0.5 * u * u).exp() * erfcx(z)
                        };
                        raw[row_off + i] = val;
                        if val > max_val {
                            max_val = val;
                        }
                    }
                }
            }

            if max_val > 0.0 && max_val.is_finite() {
                for i in 0..pts {
                    shapes[row_off + i] = raw[row_off + i] / max_val;
                }
            }
        }

        (raw, shapes)
    }

    fn build_normal_equations(&self, shapes: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let k_cnt = self.component_count;
        let dim = 1 + k_cnt;
        let pts = self.points;

        let mut design = vec![0.0; pts * dim];
        for i in 0..pts {
            design[i * dim] = 1.0;
            for k in 0..k_cnt {
                design[i * dim + 1 + k] = shapes[k * pts + i];
            }
        }

        let mut gram = vec![0.0; dim * dim];
        for i in 0..pts {
            let row = &design[i * dim..(i + 1) * dim];
            for r in 0..dim {
                let dr = row[r];
                for c in r..dim {
                    gram[r * dim + c] += dr * row[c];
                }
            }
        }
        for r in 0..dim {
            gram[r * dim + r] += RIDGE;
            for c in (r + 1)..dim {
                gram[c * dim + r] = gram[r * dim + c];
            }
        }

        (design, gram)
    }

    /// Evaluate the scaled variable-projection residual vector of length `channels * points`.
    pub fn residual(&mut self, values: &[f64]) -> Option<Vec<f64>> {
        let k_cnt = self.component_count;
        let dim = 1 + k_cnt;
        let pts = self.points;
        let ch = self.channels;

        let (raw, shapes) = self.compute_raw_and_shapes(values);
        let (design, gram) = self.build_normal_equations(&shapes);

        // rhs = D^T Y^T (dim x ch)
        let mut rhs = vec![0.0; dim * ch];
        for c in 0..ch {
            let y_c = &self.y[c * pts..(c + 1) * pts];
            for i in 0..pts {
                let yi = y_c[i];
                let d_row = &design[i * dim..(i + 1) * dim];
                for r in 0..dim {
                    rhs[r * ch + c] += d_row[r] * yi;
                }
            }
        }

        let mut gram_work = gram.clone();
        if !solve_linear_system(&mut gram_work, &mut rhs, dim, ch) {
            return None;
        }
        // rhs now holds coef (dim x ch): coef[0, c] is intercept, coef[1+k, c] is weight.
        let mut res = vec![0.0; ch * pts];
        for c in 0..ch {
            let scale = self.channel_scale[c];
            let y_c = &self.y[c * pts..(c + 1) * pts];
            let r_c = &mut res[c * pts..(c + 1) * pts];
            for i in 0..pts {
                let d_row = &design[i * dim..(i + 1) * dim];
                let mut model = rhs[c]; // intercept * 1.0
                for k in 0..k_cnt {
                    model += rhs[(1 + k) * ch + c] * d_row[1 + k];
                }
                r_c[i] = (model - y_c[i]) / scale;
            }
        }

        self.last_eval = Some(CachedEval {
            x: values.to_vec(),
            raw,
            shapes,
            design,
            gram,
        });
        Some(res)
    }

    /// Evaluate the exact Golub-Pereyra Jacobian `(channels * points, K * p)` row-major.
    pub fn jacobian(&self, values: &[f64]) -> Option<Vec<f64>> {
        let k_cnt = self.component_count;
        let p_cnt = self.shape_model.param_count();
        let col_cnt = k_cnt * p_cnt;
        let dim = 1 + k_cnt;
        let pts = self.points;
        let ch = self.channels;
        let eps = f64::EPSILON;

        let owned;
        let (raw, shapes, design, gram): (&[f64], &[f64], &[f64], &[f64]) =
            match &self.last_eval {
                Some(cached) if cached.x == values => (
                    &cached.raw,
                    &cached.shapes,
                    &cached.design,
                    &cached.gram,
                ),
                _ => {
                    let (r, s) = self.compute_raw_and_shapes(values);
                    let (d, g) = self.build_normal_equations(&s);
                    owned = (r, s, d, g);
                    (&owned.0, &owned.1, &owned.2, &owned.3)
                }
            };

        // Compute normalized shape gradients `grads[col * pts + i]` (col_cnt x pts).
        let mut grads = vec![0.0; col_cnt * pts];
        let mut raw_grad_k = vec![0.0; p_cnt * pts];

        for k in 0..k_cnt {
            let base = k * p_cnt;
            let center = values[base];
            let row_off = k * pts;

            // Find argmax and max of raw[k] (matching np.argmax: first occurrence).
            let mut max_idx = 0usize;
            let mut max_val = raw[row_off];
            for i in 1..pts {
                let v = raw[row_off + i];
                if v > max_val {
                    max_val = v;
                    max_idx = i;
                }
            }
            if !(max_val > 0.0 && max_val.is_finite()) {
                continue;
            }

            match self.shape_model {
                ShapeModel::Gaussian => {
                    let sigma = values[base + 1];
                    let inv_sigma = 1.0 / sigma;
                    for i in 0..pts {
                        let r_val = raw[row_off + i];
                        let u = (self.x_rel[i] - center) * inv_sigma;
                        raw_grad_k[i] = r_val * u * inv_sigma;
                        raw_grad_k[pts + i] = r_val * u * u * inv_sigma;
                    }
                }
                ShapeModel::BiGaussian => {
                    let s_left = values[base + 1];
                    let s_right = values[base + 2];
                    let inv_left = 1.0 / s_left;
                    let inv_right = 1.0 / s_right;
                    for i in 0..pts {
                        let r_val = raw[row_off + i];
                        let dx = self.x_rel[i] - center;
                        let left = dx < 0.0;
                        let inv_s = if left { inv_left } else { inv_right };
                        let u = dx * inv_s;
                        let sg = r_val * u * u * inv_s;
                        raw_grad_k[i] = r_val * u * inv_s;
                        raw_grad_k[pts + i] = if left { sg } else { 0.0 };
                        raw_grad_k[2 * pts + i] = if left { 0.0 } else { sg };
                    }
                }
                ShapeModel::Emg => {
                    let sigma = values[base + 1].max(eps);
                    let tau = values[base + 2].max(eps);
                    let inv_sigma = 1.0 / sigma;
                    let inv_tau = 1.0 / tau;
                    let ratio = sigma * inv_tau;
                    let inv_sqrt2 = 1.0 / SQRT_2;
                    for i in 0..pts {
                        let r_val = raw[row_off + i];
                        let u = (self.x_rel[i] - center) * inv_sigma;
                        let z = (ratio - u) * inv_sqrt2;
                        let through_z =
                            2.0 * z * r_val - TWO_OVER_SQRT_PI * (-0.5 * u * u).exp();
                        raw_grad_k[i] =
                            r_val * u * inv_sigma + through_z * inv_sigma * inv_sqrt2;
                        raw_grad_k[pts + i] = r_val * u * u * inv_sigma
                            + through_z * (inv_tau + u * inv_sigma) * inv_sqrt2;
                        raw_grad_k[2 * pts + i] =
                            -through_z * sigma * inv_tau * inv_tau * inv_sqrt2;
                    }
                }
            }

            let inv_max = 1.0 / max_val;
            for p in 0..p_cnt {
                let max_gp = raw_grad_k[p * pts + max_idx];
                let dst_off = (k * p_cnt + p) * pts;
                let src_off = p * pts;
                for i in 0..pts {
                    grads[dst_off + i] =
                        (raw_grad_k[src_off + i] - shapes[row_off + i] * max_gp) * inv_max;
                }
            }
        }

        // Solve G^{-1} D^T (dim x pts).
        let mut gram_work = gram.to_vec();
        let mut gid = vec![0.0; dim * pts];
        for r in 0..dim {
            for i in 0..pts {
                gid[r * pts + i] = design[i * dim + r];
            }
        }
        if !solve_linear_system(&mut gram_work, &mut gid, dim, pts) {
            return None;
        }

        // coef = (G^{-1} D^T) Y^T (dim x ch)
        let mut coef = vec![0.0; dim * ch];
        for r in 0..dim {
            let gid_r = &gid[r * pts..(r + 1) * pts];
            for c in 0..ch {
                let y_c = &self.y[c * pts..(c + 1) * pts];
                let mut acc = 0.0;
                for i in 0..pts {
                    acc += gid_r[i] * y_c[i];
                }
                coef[r * ch + c] = acc;
            }
        }

        // residual_c[i] = y[c, i] - (D coef)[i, c]
        let mut res_by_ch = vec![0.0; ch * pts];
        for c in 0..ch {
            let y_c = &self.y[c * pts..(c + 1) * pts];
            let rc = &mut res_by_ch[c * pts..(c + 1) * pts];
            for i in 0..pts {
                let d_row = &design[i * dim..(i + 1) * dim];
                let mut pred = coef[c];
                for k in 0..k_cnt {
                    pred += coef[(1 + k) * ch + c] * d_row[1 + k];
                }
                rc[i] = y_c[i] - pred;
            }
        }

        // Precompute G^{-1} D^T * grads^T (dim x col_cnt) once (independent of channel).
        // Because naive_{c, col}(i) = grads[col, i] * w[comp(col), c],
        // projected_{c, col}(i) = w[comp(col), c] * (grads[col, i] - (D * gid_g)[i, col]).
        let mut gid_g = vec![0.0; dim * col_cnt];
        for r in 0..dim {
            let gid_r = &gid[r * pts..(r + 1) * pts];
            for col in 0..col_cnt {
                let g_col = &grads[col * pts..(col + 1) * pts];
                let mut acc = 0.0;
                for i in 0..pts {
                    acc += gid_r[i] * g_col[i];
                }
                gid_g[r * col_cnt + col] = acc;
            }
        }

        // proj_unit[col * pts + i] = grads[col, i] - sum_r design[i, r] * gid_g[r, col]
        let mut proj_unit = grads.clone();
        for col in 0..col_cnt {
            let pu = &mut proj_unit[col * pts..(col + 1) * pts];
            for i in 0..pts {
                let d_row = &design[i * dim..(i + 1) * dim];
                let mut corr = 0.0;
                for r in 0..dim {
                    corr += d_row[r] * gid_g[r * col_cnt + col];
                }
                pu[i] -= corr;
            }
        }

        // Assemble Jacobian J ((ch * pts) x col_cnt), row-major.
        let mut jac = vec![0.0; ch * pts * col_cnt];
        for c in 0..ch {
            let inv_scale = 1.0 / self.channel_scale[c];
            let rc = &res_by_ch[c * pts..(c + 1) * pts];
            // grads_dot_r[col] = sum_i grads[col, i] * rc[i]
            let mut grads_dot_r = vec![0.0; col_cnt];
            for col in 0..col_cnt {
                let g_col = &grads[col * pts..(col + 1) * pts];
                let mut acc = 0.0;
                for i in 0..pts {
                    acc += g_col[i] * rc[i];
                }
                grads_dot_r[col] = acc;
            }

            let jac_ch_off = c * pts * col_cnt;
            for col in 0..col_cnt {
                let comp = col / p_cnt;
                let w = coef[(1 + comp) * ch + c];
                let gdr = grads_dot_r[col];
                let pu = &proj_unit[col * pts..(col + 1) * pts];
                let gid_comp = &gid[(1 + comp) * pts..(2 + comp) * pts];
                for i in 0..pts {
                    jac[jac_ch_off + i * col_cnt + col] =
                        (w * pu[i] + gid_comp[i] * gdr) * inv_scale;
                }
            }
        }

        Some(jac)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jacobian_matches_finite_differences_all_shapes() {
        let pts = 61;
        let x_rel: Vec<f64> = (0..pts).map(|i| i as f64 * 0.01).collect();
        let y: Vec<f64> = x_rel
            .iter()
            .map(|&t| {
                10.0 + 100.0 * (-0.5 * ((t - 0.25) / 0.04).powi(2)).exp()
                    + 60.0 * (-0.5 * ((t - 0.38) / 0.05).powi(2)).exp()
            })
            .collect();
        let scale = [95.0];

        let cases = [
            (ShapeModel::Gaussian, vec![0.24, 0.045, 0.39, 0.055]),
            (
                ShapeModel::BiGaussian,
                vec![0.24, 0.04, 0.05, 0.39, 0.05, 0.06],
            ),
            (ShapeModel::Emg, vec![0.24, 0.04, 0.03, 0.39, 0.05, 0.04]),
        ];

        for (model, params) in cases {
            let mut prob = VarProProblem::new(&x_rel, &y, &scale, 1, pts, 2, model);
            let _ = prob.residual(&params).expect("res");
            let jac = prob.jacobian(&params).expect("jac");
            let n = params.len();
            let h = 1e-7;
            for j in 0..n {
                let mut p_plus = params.clone();
                let mut p_minus = params.clone();
                p_plus[j] += h;
                p_minus[j] -= h;
                let f_plus = prob.residual(&p_plus).expect("f+");
                let f_minus = prob.residual(&p_minus).expect("f-");
                for i in 0..pts {
                    let fd = (f_plus[i] - f_minus[i]) / (2.0 * h);
                    let ana = jac[i * n + j];
                    assert!(
                        (ana - fd).abs() < 1e-5 * fd.abs().max(1.0),
                        "shape={model:?} row={i} col={j} ana={ana} fd={fd}"
                    );
                }
            }
        }
    }
}
