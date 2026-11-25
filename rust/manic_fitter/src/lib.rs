//! C ABI entry point for chromatographic peak shape fitting.
//!
//! Replaces the inner `scipy.optimize.least_squares` (TRF with bounds and
//! Golub-Pereyra variable projection) call in
//! `manic.processors.chromatographic_peak_deconvolution._fit_shape_candidate`.

pub mod erfc;
pub mod linalg;
pub mod shapes;
pub mod trf;

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::slice;

use shapes::{ShapeModel, VarProProblem};
use trf::solve_trf_bounds;

/// Fit one candidate shape model with bounded Trust-Region Reflective least squares.
///
/// # Safety
/// All non-null input pointers must point to valid contiguous `f64` buffers of
/// the specified lengths, and `out_x_ptr` / `out_status_ptr` must be valid
/// writable buffers for `component_count * param_count` and `1` elements.
///
/// Returns:
/// - `1` on solver completion (caller inspects `*out_status_ptr`, using SciPy
///   status codes: `0`=max_nfev, `1`=gtol, `2`=ftol, `3`=xtol, `4`=both),
/// - `0` on invalid input or expected solver failure (e.g. singular system),
/// - `-1` if an internal Rust panic was caught across the FFI boundary.
#[no_mangle]
pub unsafe extern "C" fn manic_fit_shape_candidate(
    x_rel_ptr: *const f64,
    points: usize,
    y_ptr: *const f64,
    channels: usize,
    channel_scale_ptr: *const f64,
    shape_model_code: i32,
    initial_ptr: *const f64,
    lower_ptr: *const f64,
    upper_ptr: *const f64,
    component_count: usize,
    max_nfev: usize,
    out_x_ptr: *mut f64,
    out_status_ptr: *mut i32,
) -> i32 {
    if x_rel_ptr.is_null()
        || y_ptr.is_null()
        || channel_scale_ptr.is_null()
        || initial_ptr.is_null()
        || lower_ptr.is_null()
        || upper_ptr.is_null()
        || out_x_ptr.is_null()
        || out_status_ptr.is_null()
        || points == 0
        || channels == 0
        || component_count == 0
        || max_nfev == 0
    {
        return 0;
    }

    let shape_model = match ShapeModel::from_code(shape_model_code) {
        Some(m) => m,
        None => return 0,
    };
    let n_params = match component_count.checked_mul(shape_model.param_count()) {
        Some(n) if n > 0 => n,
        _ => return 0,
    };
    let y_len = match channels.checked_mul(points) {
        Some(n) if n > 0 => n,
        _ => return 0,
    };

    let x_rel = slice::from_raw_parts(x_rel_ptr, points);
    let y = slice::from_raw_parts(y_ptr, y_len);
    let channel_scale = slice::from_raw_parts(channel_scale_ptr, channels);
    let initial = slice::from_raw_parts(initial_ptr, n_params);
    let lower = slice::from_raw_parts(lower_ptr, n_params);
    let upper = slice::from_raw_parts(upper_ptr, n_params);
    let out_x = slice::from_raw_parts_mut(out_x_ptr, n_params);

    let result = catch_unwind(AssertUnwindSafe(|| {
        let mut prob = VarProProblem::new(
            x_rel,
            y,
            channel_scale,
            channels,
            points,
            component_count,
            shape_model,
        );
        solve_trf_bounds(&mut prob, initial, lower, upper, max_nfev)
    }));

    match result {
        Ok(Some(res)) if res.x.len() == out_x.len() => {
            out_x.copy_from_slice(&res.x);
            *out_status_ptr = res.status;
            1
        }
        Ok(_) => 0,
        Err(_) => -1,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recovers_two_overlapping_gaussians() {
        let pts = 101;
        let x_rel: Vec<f64> = (0..pts).map(|i| i as f64 * 0.01).collect();
        let y: Vec<f64> = x_rel
            .iter()
            .map(|&t| {
                5.0 + 1000.0 * (-0.5 * ((t - 0.42) / 0.04).powi(2)).exp()
                    + 600.0 * (-0.5 * ((t - 0.56) / 0.05).powi(2)).exp()
            })
            .collect();
        let scale = [950.0];
        let initial = [0.40, 0.05, 0.58, 0.05];
        let lower = [0.0, 0.01, 0.0, 0.01];
        let upper = [1.0, 0.3, 1.0, 0.3];
        let mut out_x = [0.0; 4];
        let mut status = -1;

        let ok = unsafe {
            manic_fit_shape_candidate(
                x_rel.as_ptr(),
                pts,
                y.as_ptr(),
                1,
                scale.as_ptr(),
                0,
                initial.as_ptr(),
                lower.as_ptr(),
                upper.as_ptr(),
                2,
                240,
                out_x.as_mut_ptr(),
                &mut status,
            )
        };
        assert_eq!(ok, 1);
        assert!(status > 0);
        assert!((out_x[0] - 0.42).abs() < 1e-4);
        assert!((out_x[1] - 0.04).abs() < 1e-4);
        assert!((out_x[2] - 0.56).abs() < 1e-4);
        assert!((out_x[3] - 0.05).abs() < 1e-4);
    }

    #[test]
    fn recovers_emg_peak() {
        let pts = 101;
        let x_rel: Vec<f64> = (0..pts).map(|i| i as f64 * 0.01).collect();
        let true_params = [0.45, 0.03, 0.05];
        // Generate synthetic EMG trace via erfc/erfcx.
        let mut raw = vec![0.0; pts];
        let mut max_v = 0.0f64;
        for i in 0..pts {
            let u = (x_rel[i] - true_params[0]) / true_params[1];
            let ratio = true_params[1] / true_params[2];
            let z = (ratio - u) / std::f64::consts::SQRT_2;
            let v = if z < 0.0 {
                (0.5 * ratio * ratio - u * ratio).min(0.0).exp() * erfc::erfc(z)
            } else {
                (-0.5 * u * u).exp() * erfc::erfcx(z)
            };
            raw[i] = v;
            max_v = max_v.max(v);
        }
        let y: Vec<f64> = raw.iter().map(|&v| 12.0 + 800.0 * (v / max_v)).collect();
        let scale = [750.0];
        let initial = [0.48, 0.04, 0.04];
        let lower = [0.0, 0.01, 0.01];
        let upper = [1.0, 0.3, 1.2];
        let mut out_x = [0.0; 3];
        let mut status = -1;

        let ok = unsafe {
            manic_fit_shape_candidate(
                x_rel.as_ptr(),
                pts,
                y.as_ptr(),
                1,
                scale.as_ptr(),
                2,
                initial.as_ptr(),
                lower.as_ptr(),
                upper.as_ptr(),
                1,
                240,
                out_x.as_mut_ptr(),
                &mut status,
            )
        };
        assert_eq!(ok, 1);
        assert!(status > 0);
        assert!((out_x[0] - true_params[0]).abs() < 1e-4);
        assert!((out_x[1] - true_params[1]).abs() < 1e-4);
        assert!((out_x[2] - true_params[2]).abs() < 1e-4);
    }
}
