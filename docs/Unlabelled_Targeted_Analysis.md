# Unlabelled Targeted Analysis

This guide explains MANIC's **unlabelled** (targeted) mode: the science behind
quantifier and qualifier ions, how to prepare a compound list, how to review
results in the application, and how to interpret the Excel export.

Use this mode for targeted GC-MS profiling of known compounds when you are
**not** performing stable-isotope tracing. For isotope-tracing workflows, use
**labelled** mode instead.

---

## 1. What this mode is for

In unlabelled mode MANIC answers two questions for each target compound in each
sample:

1. **How much signal is there?** — quantified from one chosen ion (the Q ion).
2. **Is that signal consistent with the intended compound?** — checked with
   retention time and one or more qualifier ions (V ions).

It does **not**:

- extract consecutive isotopologue channels (M+0, M+1, …)
- apply natural-abundance correction
- calculate % label incorporation or carbon enrichment
- claim library-spectrum identification

Identity checks here are **supporting evidence**. They do not replace a spectral
library match when that is required by your laboratory practice or regulatory
context.

---

## 2. The science in plain language

### Electron-ionization fragments

In GC-MS with electron ionization (EI), a molecule breaks into charged fragments.
Each fragment has a characteristic mass-to-charge ratio (*m/z*). A pure compound
produces a reproducible **fragmentation fingerprint**: the same ions, in roughly
the same relative abundances, every time it is measured under the same
conditions.

### Quantifier ion (Q ion)

The **Q ion** is the fragment you choose to **measure amount**.

Good Q ions are usually:

- intense (good signal-to-noise)
- specific enough for the chromatographic context
- free of strong co-eluting interference at that *m/z*

In MANIC, the **reported peak area and any semi-quantitative amount come from
the Q ion alone**. Qualifier ions never add to the quantified response.

### Qualifier ions (V ions)

**V ions** (historically *validation ions* in old MANIC) are secondary fragments
used to **support identity**.

Because fragmentation is characteristic, the ratio

\[
\frac{\text{area of V ion}}{\text{area of Q ion}}
\]

should stay close to a reference value for that compound under the method. If a
co-eluting interference contributes to one channel but not the other, the ratio
drifts and MANIC flags the result for review.

MANIC accepts one or two V ions. Old MANIC required two; pythonMANIC requires at
least one.

### Retention time

Chromatographic retention time (RT) is a second, independent identity check.
MANIC compares the **observed Q-ion apex** inside the integration window with
the **current tR** — the same value used to centre the window. Changing tR
updates integration and identity QC together, as in labelled mode. Reset
restores the compound-list default.

### Why labelled mode does not use V ions

In labelled mode the channels are consecutive isotopologues of the **same**
fragment (M+0, M+1, …). Their relative areas are the biological labelling
signal, not a fixed chemical fingerprint. Identity is carried by the
experimental design (known targets / standards) and by the isotopologue envelope
itself. Applying Q/V ratio logic there would confuse biology with identity QC.

### Why deconvolution is off

Unlabelled compounds are imported with `deconvolution_level = off`. Each Q or V
ion is integrated over the fixed window.

Labelled deconvolution fits each isotopologue on its own EIC. Channels do not
share an elution shape. That independent path is not switched on for unlabelled
import yet. A joint shared-shape fit on Q/V ions would still be wrong, because
those ions are different fragments and their areas must stay independent for
V/Q identity QC.

---

## 3. Choosing a mode

When MANIC starts, you choose **Labelled** or **Unlabelled**. The mode is fixed
for that analysis session so the same ion signals cannot be interpreted under
two scientific models.

To switch modes later:

1. **File → New Analysis Session…**
2. Confirm that the current session will be cleared
3. Choose the new mode

If you load a compound list written for the other workflow, MANIC sniffs the
headers and offers to start a matching session instead of misinterpreting the
file.

The window title always shows the active mode
(e.g. `MANIC v… — Unlabelled analysis`).

---

## 4. Compound list format

Prepare an Excel (`.xlsx`, `.xls`) or CSV (`.csv`) file. Headers are
case-insensitive and ignore spaces or underscores
(`QIon`, `q_ion`, and `quant_ion` are treated the same after normalisation).

### Required columns

| Column | Accepted aliases | Meaning |
| :--- | :--- | :--- |
| `name` | | Unique compound identifier |
| `tR` | | Default retention time (minutes); Apply can override this per sample |
| `lOffset` | | Left integration half-window (minutes) from tR |
| `rOffset` | | Right integration half-window (minutes) from tR |
| `QIon` | `quant_ion` | Quantifier *m/z* |
| `ValIon1` | `qualifier_ion_1` | First qualifier *m/z* |

### Optional columns

| Column | Accepted aliases | Meaning |
| :--- | :--- | :--- |
| `ValIon2` | `qualifier_ion_2` | Second qualifier *m/z* |
| `Qualifier 1 Ratio` | | Expected V1/Q area ratio |
| `Qualifier 1 Tolerance` | | Fractional tolerance on that ratio (e.g. `0.30` = ±30%) |
| `Qualifier 2 Ratio` | | Expected V2/Q area ratio |
| `Qualifier 2 Tolerance` | | Fractional tolerance on V2/Q |
| `tR Window` | `tR_Window` | RT identity tolerance (minutes). If omitted, defaults to `max(lOffset, rOffset)` |
| `Amount in StdMix` | | Concentration of the compound in the standard mixture (for semi-quant) |
| `Int Std amount` | | Amount of internal standard added to samples |
| `MM Files` | | Pattern matching standard-mixture sample names (wildcards allowed, e.g. `*_MM_*`) |

### Minimal example

```csv
name,tR,lOffset,rOffset,QIon,ValIon1,ValIon2,Qualifier 1 Ratio,Qualifier 1 Tolerance,tR Window
Citrate 4TMS,12.40,0.12,0.12,273,147,73,0.42,0.25,0.10
```

### Scientific constraints enforced on import

- Exactly one Q ion and at least one V ion
- All ion *m/z* values must be positive and distinct
- Ions must resolve to **distinct nominal mass bins** (extraction matches on
  integer *m/z*; e.g. 217.1 and 217.4 are not allowed together)
- Ratio tolerances cannot be negative

### Choosing expected ratios and tolerances

Typical practice:

1. Measure V/Q area ratios across several clean injections of standards or
   well-characterised samples.
2. Use a robust central value (e.g. median) as `Qualifier N Ratio`.
3. Set `Qualifier N Tolerance` as a **fraction of the expected ratio**.
   MANIC accepts a ratio if

   \[
   |\text{observed} - \text{expected}| \le
   \begin{cases}
   \text{tolerance} & \text{if expected} = 0 \\
   |\text{expected}| \times \text{tolerance} & \text{otherwise}
   \end{cases}
   \]

   Example: expected `0.40`, tolerance `0.25` → allowed range
   \(0.40 \pm 0.10\) i.e. 0.30–0.50.

Regulatory guidance for pesticide residues often cites relative ion-ratio
tolerances around ±30%; many metabolomics methods use similar or wider windows
depending on matrix and instrument stability. Choose values that reflect *your*
method, not a universal constant.

Repository helper scripts under `scripts/` can build and calibrate draft lists
from CDF data for testing; laboratory methods should still be curated by an
analyst.

---

## 5. End-to-end workflow

### Step A — Start an unlabelled session

Launch MANIC (or use **File → New Analysis Session…**) and choose
**Unlabelled targeted analysis**.

### Step B — Load the compound list

**File → Load Compounds/Parameter List** and select your Gv3-style file.

Verification:

- The compounds status indicator turns green
- The compound list populates
- Selecting a compound shows its Q/V *m/z* in the sidebar indicator

### Step C — Load raw CDF data

**File → Load Raw Data (CDF)** and select the **folder** containing NetCDF
(`.cdf`) files.

MANIC extracts one multi-channel EIC per compound per sample: channel 0 is the
Q ion, subsequent channels are V ions in ordinal order. The extraction window
is widened if needed so configured `lOffset` / `rOffset` are not clipped.

Natural-abundance correction is **not** applied in this mode.

### Step D — Review compounds

1. Select a compound and the samples of interest.
2. Inspect the EIC tiles and the **Targeted identity QC** table in the left
   sidebar.
3. Adjust tR or offsets where peaks have drifted, then
   **Apply**.
4. Use display aids as needed:
   - **Shared y-scale** — compare abundances across samples on one intensity
     scale
   - **Normalize Q/V shapes** — display-only scaling of V traces to Q peak
     height for shape / apex comparison (does **not** change areas)

### Step E — Export

Export the Excel workbook when review is complete. Unlabelled sessions write
three sheets (see [§8](#8-excel-export)).

---

## 6. Integration semantics

Two times appear in the UI. They use the same tR that labelled mode uses.

| Concept | Source | Role |
| :--- | :--- | :--- |
| **tR** | Compound list, then any per-sample override you Apply | Centre of the integration window and expected RT for identity QC |
| **Observed Q apex** | Maximum of the Q-ion trace inside the window | Measured peak position |

Integration boundaries are:

\[
[\mathrm{tR} - \text{lOffset},\;
 \mathrm{tR} + \text{rOffset}]
\]

Changing tR moves the window and the identity target together. The RT check
compares **observed Q apex** with the **current tR**, using `tR Window` (or
the default above) as tolerance:

\[
\Delta\mathrm{RT} = \mathrm{RT}_{\text{observed}} - \mathrm{tR}
\]

passes when \(|\Delta\mathrm{RT}| \le \mathrm{RT\ tolerance}\). Reset restores
the compound-list tR.

---

## 7. Identity QC statuses

For each sample × compound, MANIC assesses:

1. Is the Q ion detected above the assessment floor?
2. If RT references are configured: does \(\Delta\mathrm{RT}\) pass?
3. For each V ion with both expected ratio and tolerance: does the observed
   V/Q ratio pass?

| Status | Meaning |
| :--- | :--- |
| **Supported** | Q detected; every configured RT and ratio check passed |
| **Review required** | Q detected, but at least one configured check failed |
| **Not detected** | Q-ion area at or below the assessment floor |
| **Not assessed** | Q detected, but identity references are incomplete (e.g. missing expected ratios), so MANIC reports signal without confirmation |
| **Unavailable** | QC could not be computed (missing EIC / compound data) |

Click a QC table row to see the full reason text and highlight that sample's
plot. Use **Show issues only** to hide supported samples while reviewing.

Tile borders summarise the same statuses (amber for review, grey for not
detected). Peak-height validation against an internal standard (red tint when
enabled) remains a separate check and uses **Q-ion area only**.

---

## 8. Excel export

Unlabelled exports contain three worksheets.

### Targeted Results

One row per sample × compound:

| Column | Content |
| :--- | :--- |
| Q Ion m/z / Area | Quantifier definition and integrated area |
| Response Ratio to Internal Standard | Q area ÷ internal-standard Q area (when an IS is set) |
| Estimated Amount | Semi-quantitative estimate when calibration metadata and a response factor are available |
| Result Type | What the numeric columns represent (see below) |
| Identity Status / Observed RT / RT Error / Identity Reasons | Identity QC summary |

**Result Type** values:

- `Q ion peak area` — only the raw Q response is available
- `Relative response ratio` — IS ratio available, but not a calibrated amount
- `Semi-quantitative estimate (single-point RF)` — amount from a measured
  single-point response factor
- `Uncalibrated estimate (response factor assumed = 1.0)` — amount computed
  with an assumed RF of 1.0 when no measured factor was available; treat with
  caution

Semi-quantitative amounts are **not** multi-point calibration-curve results.
Report them as estimates unless your laboratory has separately validated the
calibration.

### Qualifier QC

Long-form V-ion ratios: observed ratio, expected ratio, fractional tolerance,
and `PASS` / `REVIEW` / `N/A`.

### Targeted Method

Human-readable interpretation limits, then two tables:

- **Ion definitions** — one row per Q/V channel (role, ordinal, *m/z*,
  expected ratios, RT tolerance)
- **Current tR** — one row per sample × compound, the session `tR` used for
  integration and identity QC after Apply

A session changelog is also written; for unlabelled mode it states that
Q-ion area alone supplies the analytical response, V ions are identity
evidence, current tR is used for both integration and identity RT QC, and
natural-isotope correction / isotopologue deconvolution are not applied.

---

## 9. Reading the plots

### Main grid (sample tiles)

Typical guide lines:

| Guide | Appearance | Meaning |
| :--- | :--- | :--- |
| tR | Black | Centre of the integration window and identity expected RT |
| Left / right offsets | Blue dashed | Integration boundaries |
| Observed Q apex | Magenta solid | Measured Q-ion apex inside the window |

Trace colours follow the shared channel palette (Q is the first colour; V1 is
typically the second). The observed-apex guide uses **magenta** so it is not
confused with the orange V1 trace.

The channel legend above the grid names each Q/V *m/z*.

### Detail dialog

Right-click a tile for the detail view:

- EIC with the same tR / offset / apex guides
- TIC (when available)
- Mass spectrum taken at the **observed Q apex** when available (otherwise at
  tR)

---

## 10. Practical review checklist

1. **Supported samples** — spot-check a few; confirm the magenta apex sits on a
   clean Q peak and V traces share the same apex shape.
2. **Review required** — read the reasons. RT failures often need a shifted
   tR so the window covers the peak.
   Ratio failures often indicate co-elution, wrong V ion, or an outdated
   expected ratio.
3. **Not detected** — confirm absence vs. window missed the peak vs. wrong Q
   *m/z*.
4. **Not assessed** — add expected ratios / tolerances (and a sensible
   `tR Window`) if you want automated confirmation.
5. Before trusting amounts — confirm the internal standard, `MM Files`
   patterns, and whether Result Type says *semi-quantitative* or
   *uncalibrated*.

---

## 11. Unlabelled vs labelled vs old MANIC

| Topic | Unlabelled (this mode) | Labelled | Old MANIC Gv3 (historical) |
| :--- | :--- | :--- | :--- |
| Channels | Q + V diagnostic ions | M+0…M+n isotopologues | Q + ValIon1 + ValIon2 |
| Quantification | Q-ion area only | Sum / distribution across isotopologues | Q (+ visual V overlay) |
| Identity | RT + optional V/Q ratios | Envelope / experimental design | Visual V scaling; no automated ratio QC |
| Natural-abundance correction | Off | On | N/A for Gv3 unlabelled |
| Deconvolution | Off | Optional per compound | N/A |
| Export | Targeted Results / Qualifier QC / Method | Isotope-tracing sheets | Legacy MATLAB exports |

Old MANIC Gv3 lists (exactly
`name, tR, lOffset, rOffset, QIon, ValIon1, ValIon2, tR_Window`) import into
pythonMANIC; ratio columns can be added to enable automated identity QC that
old MANIC did not perform.

---

## 12. Limitations (read before publishing numbers)

- Identity QC supports identification; it does **not** replace library matching
  when your SOP requires it.
- Fixed-window integration assumes the peak lies inside
  centre ± offsets. Large RT drift needs per-sample centre adjustment.
- Co-elution that affects Q and V proportionally can still pass ratio checks —
  visual review of shapes remains important (**Normalize Q/V shapes** helps).
- Semi-quantitative amounts use a single-point response factor (or an assumed
  factor of 1.0). They are estimates unless independently validated.
- Mode is session-scoped: do not mix labelled and unlabelled interpretation of
  the same raw channels in one session.

---

## Related documentation

- [User Guide](01_user_guide.md) — general application workflow (labelled-oriented steps still apply for CDF import mechanics)
- [Peak Validation](Reference_Peak_Validation.md) — internal-standard height checks (unlabelled uses Q-ion area)
- [Integration Methods](Reference_Integration_Methods.md) — time-based vs legacy unit-spacing integration
- [Baseline Correction](Reference_Baseline_Correction.md) — optional linear baseline subtraction
- [Mass Tolerance](Reference_Mass_Tolerance.md) — how *m/z* values are binned on import
