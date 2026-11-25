//! High-precision `erfc` and `erfcx` based on W. J. Cody's rational Chebyshev
//! approximations (Math. Comp. 23, 1969, pp. 631-637; SPECFUN CALERF).
//!
//! Matches `scipy.special.erfc` (to ~3e-16 for `z < 0`) and
//! `scipy.special.erfcx` (to ~1e-15 for `z >= 0`), the domain used by EMG,
//! with zero external dependencies.

const THRESH: f64 = 0.46875;
const XBIG: f64 = 26.543;
const XHUGE: f64 = 6.71e7;
const XMAX: f64 = 2.53e307;
const XNEG: f64 = -26.628;
const SQRPI: f64 = 5.6418958354775628695e-1; // 1 / sqrt(pi)

const A: [f64; 5] = [
    3.16112374387056560e00,
    1.13864154151050156e02,
    3.77485237685302021e02,
    3.20937758913846947e03,
    1.85777706184603153e-1,
];
const B: [f64; 4] = [
    2.36012909523441209e01,
    2.44024637934444173e02,
    1.28261652607737228e03,
    2.84423683343917062e03,
];

const C: [f64; 9] = [
    5.64188496988670089e-1,
    8.88314979438837594e00,
    6.61191906371416295e01,
    2.98635138197400131e02,
    8.81952221241769090e02,
    1.71204761263407058e03,
    2.05107837782607147e03,
    1.23033935479799725e03,
    2.15311535474403846e-8,
];
const D: [f64; 8] = [
    1.57449261107098347e01,
    1.17693950891312499e02,
    5.37181101862009858e02,
    1.62138957456669019e03,
    3.29079923573345963e03,
    4.36261909014324716e03,
    3.43936767414372164e03,
    1.23033935480374942e03,
];

const P: [f64; 6] = [
    3.05326634961232344e-1,
    3.60344899949804439e-1,
    1.25781726111229246e-1,
    1.60837851487422766e-2,
    6.58749161529837803e-4,
    1.63153871373020978e-2,
];
const Q: [f64; 5] = [
    2.56852019228982242e00,
    1.87295284992346047e00,
    5.27905102951428412e-1,
    6.05183413124413191e-2,
    2.33520497626869185e-3,
];

#[inline]
fn asymptotic_erfcx(y: f64) -> f64 {
    let ysq = 1.0 / (y * y);
    let mut xnum = P[5] * ysq;
    let mut xden = ysq;
    for i in 0..4 {
        xnum = (xnum + P[i]) * ysq;
        xden = (xden + Q[i]) * ysq;
    }
    let ratio = ysq * (xnum + P[4]) / (xden + Q[4]);
    (SQRPI - ratio) / y
}

/// Evaluate `erfc(x)` (`jint = 1`) or `erfcx(x)` (`jint = 2`).
fn calerf(arg: f64, jint: i32) -> f64 {
    if arg.is_nan() {
        return f64::NAN;
    }
    let x = arg;
    let y = x.abs();
    let mut result: f64;

    if y <= THRESH {
        let mut ysq = 0.0;
        if y > 1.11e-16 {
            ysq = y * y;
        }
        let mut xnum = A[4] * ysq;
        let mut xden = ysq;
        for i in 0..3 {
            xnum = (xnum + A[i]) * ysq;
            xden = (xden + B[i]) * ysq;
        }
        result = x * (xnum + A[3]) / (xden + B[3]);
        if jint != 0 {
            result = 1.0 - result;
        }
        if jint == 2 {
            result *= (y * y).exp();
        }
        return result;
    }

    if y <= 4.0 {
        let mut xnum = C[8] * y;
        let mut xden = y;
        for i in 0..7 {
            xnum = (xnum + C[i]) * y;
            xden = (xden + D[i]) * y;
        }
        result = (xnum + C[7]) / (xden + D[7]);
        if jint != 2 {
            let ysq = (y * 16.0).trunc() / 16.0;
            let del = (y - ysq) * (y + ysq);
            result = (-ysq * ysq).exp() * (-del).exp() * result;
        }
    } else if y >= XBIG {
        if jint != 2 || y >= XMAX {
            result = 0.0;
        } else if y >= XHUGE {
            result = SQRPI / y;
        } else {
            result = asymptotic_erfcx(y);
        }
    } else {
        result = asymptotic_erfcx(y);
        if jint != 2 {
            let ysq_t = (y * 16.0).trunc() / 16.0;
            let del = (y - ysq_t) * (y + ysq_t);
            result = (-ysq_t * ysq_t).exp() * (-del).exp() * result;
        }
    }

    if jint == 1 {
        if x < 0.0 {
            result = 2.0 - result;
        }
    } else if jint == 2 && x < 0.0 {
        if x < XNEG {
            result = f64::INFINITY;
        } else {
            let ysq = (x * 16.0).trunc() / 16.0;
            let del = (x - ysq) * (x + ysq);
            let y_exp = (ysq * ysq).exp() * del.exp();
            result = (y_exp + y_exp) - result;
        }
    }

    result
}

#[inline]
pub fn erfc(x: f64) -> f64 {
    calerf(x, 1)
}

#[inline]
pub fn erfcx(x: f64) -> f64 {
    calerf(x, 2)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn erfc_and_erfcx_known_values() {
        assert!((erfc(0.0) - 1.0).abs() < 1e-15);
        assert!((erfcx(0.0) - 1.0).abs() < 1e-15);
        // erfc(1) = 0.15729920705028513
        assert!((erfc(1.0) - 0.15729920705028513).abs() < 1e-15);
        // erfc(-1) = 2 - erfc(1)
        assert!((erfc(-1.0) - (2.0 - 0.15729920705028513)).abs() < 1e-15);
        // erfcx(1) = exp(1) * erfc(1) = 0.427583576155807
        assert!((erfcx(1.0) - 0.427583576155807).abs() < 1e-14);
        // erfcx(10) = 0.05614099274382094
        assert!((erfcx(10.0) - 0.05614099274382094).abs() < 1e-14);
        // erfcx(100) from scipy.special.erfcx(100.0)
        let got_100 = erfcx(100.0);
        let expected_100 = 0.005641613782989433_f64;
        assert!(
            (got_100 - expected_100).abs() < 1e-15,
            "got={got_100} expected={expected_100}"
        );
        // erfc(30) underflows to 0
        assert_eq!(erfc(30.0), 0.0);
        // erfc(-30) = 2.0
        assert_eq!(erfc(-30.0), 2.0);
    }
}
