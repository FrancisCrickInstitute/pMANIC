"""
Natural isotope abundance correction for isotopologue analysis.

This module implements theoretical correction for natural isotope abundances
based on known isotope distributions. The correction removes the contribution
of natural heavy isotopes (e.g., 13C, 2H, 15N) from measured isotopologue
distributions to reveal true experimental labeling.
"""

import logging
import re
from typing import Dict, Tuple

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class NaturalAbundances:
    """Natural isotope abundances for common elements."""

    def __init__(self):
        # Format: [mass0, mass+1, mass+2, ...]
        self.C = np.array([0.9893, 0.0107])  # 12C, 13C
        self.H = np.array([0.99985, 0.00015])  # 1H, 2H
        self.N = np.array([0.99632, 0.00368])  # 14N, 15N
        self.O = np.array([0.99757, 0.00038, 0.00205])  # 16O, 17O, 18O
        self.Si = np.array([0.922297, 0.046832, 0.030872])  # 28Si, 29Si, 30Si
        self.S = np.array(
            [0.9493, 0.0076, 0.0429, 0, 0.0002]
        )  # 32S, 33S, 34S, 35S, 36S
        self.P = np.array([1.0])  # 31P (monoisotopic)


class NaturalAbundanceCorrector:
    """
    Corrects isotopologue distributions for natural abundance.

    This class implements the theoretical correction approach using
    convolution-based matrix construction and constrained optimization
    to deconvolute natural abundance from experimental labeling.
    """

    def __init__(self):
        self.abundances = NaturalAbundances()

    def parse_formula(self, formula: str) -> Dict[str, int]:
        """
        Parse molecular formula string into element counts.

        Handles both standard format (C6H12O6) and space-separated format
        (C6 H12 O6 or C6 O3 N1 H12 Si1 S0 P0).

        Args:
            formula: Molecular formula string

        Returns:
            Dictionary of element symbols to counts
        """
        if not formula:
            return {}

        # Remove spaces if present (for space-separated format)
        formula_clean = formula.replace(" ", "")

        # Parse elements and counts using regex
        # Matches element symbols (with optional lowercase) followed by optional numbers
        pattern = r"([A-Z][a-z]?)(\d*)"
        matches = re.findall(pattern, formula_clean)

        elements = {}
        for element, count_str in matches:
            # Skip if element is just whitespace or empty
            if not element or element.isspace():
                continue

            # Parse count (default to 1 if not specified)
            count = int(count_str) if count_str else 1

            # Store or update count
            if element in elements:
                elements[element] += count
            else:
                elements[element] = count

        return elements

    def calculate_derivative_formula(
        self, base_formula: str, tbdms: int = 0, meox: int = 0, me: int = 0
    ) -> Tuple[str, Dict[str, int]]:
        """
        Calculate molecular formula after derivatization.

        Derivatization groups modify the molecular formula:
        - TBDMS (tert-butyldimethylsilyl): Protects -OH groups, adds C6H15Si per group
        - MeOX (methoxyamine): Derivatizes carbonyls, adds CH3ON per group
        - Me (methyl): Adds CH2 per methylation

        Args:
            base_formula: Base molecular formula
            tbdms: Number of TBDMS groups
            meox: Number of methoxyamine groups
            me: Number of methylations

        Returns:
            Tuple of (formula string, element dict)
        """
        elements = self.parse_formula(base_formula)

        # Apply TBDMS derivatization
        # Each TBDMS adds C6H15Si but replaces an H
        if tbdms > 0:
            elements["C"] = elements.get("C", 0) + tbdms * 6
            elements["H"] = (
                elements.get("H", 0) + tbdms * 15 - tbdms
            )  # Minus H replaced
            elements["Si"] = elements.get("Si", 0) + tbdms

        # Apply MeOX derivatization
        # Adds CH3ON per carbonyl
        if meox > 0:
            elements["C"] = elements.get("C", 0) + meox
            elements["H"] = elements.get("H", 0) + meox * 3
            elements["O"] = elements.get("O", 0) + meox
            elements["N"] = elements.get("N", 0) + meox

        # Apply methylation
        # Adds CH2 per methylation
        if me > 0:
            elements["C"] = elements.get("C", 0) + me
            elements["H"] = elements.get("H", 0) + me * 2

        # Build formula string in standard order
        formula_str = ""
        element_order = ["C", "H", "N", "O", "S", "Si", "P"]

        for elem in element_order:
            if elem in elements and elements[elem] > 0:
                count = elements[elem]
                if count == 1:
                    formula_str += elem
                else:
                    formula_str += f"{elem}{count}"

        # Add any remaining elements not in standard order
        for elem in sorted(elements.keys()):
            if elem not in element_order and elements[elem] > 0:
                count = elements[elem]
                if count == 1:
                    formula_str += elem
                else:
                    formula_str += f"{elem}{count}"

        return formula_str, elements

    def build_correction_matrix(
        self,
        formula: str,
        label_element: str,
        label_atoms: int,
        label_purity: np.ndarray = None,
        max_isotopologues: int = None,
    ) -> np.ndarray:
        """
        Build correction matrix for natural abundance using convolution.

        The correction matrix transforms measured isotopologue distributions
        to true labeled distributions by accounting for natural abundance.

        Matrix structure:
        - Each column represents the expected measured pattern for a pure M+i species
        - Element M[i,j] is the contribution of true M+j to measured M+i

        Args:
            formula: Molecular formula (after derivatization)
            label_element: Element being labeled (typically 'C')
            label_atoms: Number of positions that can be labeled
            label_purity: Isotope purity [unlabeled, labeled] (default [0.01, 0.99])
            max_isotopologues: Maximum number of isotopologues to consider

        Returns:
            Correction matrix of shape (n_isotopologues, n_isotopologues)
        """
        if label_purity is None:
            label_purity = np.array([0.01, 0.99])  # 99% isotope purity

        elements = self.parse_formula(formula)

        # Determine matrix size
        n_isotopologues = label_atoms + 1
        if max_isotopologues:
            n_isotopologues = min(n_isotopologues, max_isotopologues)

        # Calculate natural abundance distribution for unlabeled atoms
        # Start with delta function [1.0]
        nat_dist = np.array([1.0])

        for element, count in elements.items():
            # For the labeled element, exclude labeled positions
            if element == label_element:
                unlabeled_count = max(0, count - label_atoms)
            else:
                unlabeled_count = count

            # Convolve with element's isotope distribution
            if unlabeled_count > 0 and hasattr(self.abundances, element):
                elem_dist = getattr(self.abundances, element)
                for _ in range(unlabeled_count):
                    nat_dist = np.convolve(nat_dist, elem_dist)

        # Build correction matrix column by column
        correction_matrix = np.zeros((n_isotopologues, n_isotopologues))

        for n_labeled in range(n_isotopologues):
            # Start with natural abundance of unlabeled atoms
            column = nat_dist.copy()

            # Add contribution from labeled atoms
            if n_labeled > 0 and hasattr(self.abundances, label_element):
                # Convolve with labeled element distribution n_labeled times
                elem_dist = getattr(self.abundances, label_element)
                for _ in range(n_labeled):
                    column = np.convolve(column, elem_dist)

            # Apply label purity (imperfect labeling)
            # Each labeled position has probability distribution given by label_purity
            for _ in range(1, n_labeled + 1):
                column = np.convolve(column, label_purity)

            # Truncate or pad to matrix size
            if len(column) >= n_isotopologues:
                correction_matrix[:, n_labeled] = column[:n_isotopologues]
            else:
                correction_matrix[: len(column), n_labeled] = column

        return correction_matrix

    def correct_isotopologue_distribution(
        self,
        measured: np.ndarray,
        correction_matrix: np.ndarray,
        preserve_total: bool = True,
    ) -> np.ndarray:
        """
        Apply natural abundance correction to measured isotopologue distribution.

        Uses constrained optimization to solve:
        correction_matrix @ true_distribution = measured_distribution

        Args:
            measured: Measured isotopologue intensities (not necessarily normalized)
            correction_matrix: Matrix from build_correction_matrix
            preserve_total: If True, preserve total intensity; if False, normalize to 1

        Returns:
            Corrected isotopologue distribution
        """
        # Handle edge cases
        if np.sum(measured) == 0:
            return measured

        # Store total for later
        total_intensity = np.sum(measured)

        # Normalize for optimization (improves numerical stability)
        if preserve_total:
            measured_norm = measured / total_intensity
        else:
            measured_norm = measured / np.sum(measured)

        # Define objective function (least squares)
        def objective(x):
            predicted = correction_matrix @ x
            residual = measured_norm - predicted
            return np.sum(residual**2)

        # Set up constraints
        constraints = []
        if preserve_total:
            # Sum to 1 (will rescale later)
            constraints.append({"type": "eq", "fun": lambda x: np.sum(x) - 1.0})
        else:
            # Sum to 1
            constraints.append({"type": "eq", "fun": lambda x: np.sum(x) - 1.0})

        # Bounds: all values must be non-negative
        bounds = [(0, None) for _ in range(len(measured))]

        # Initial guess: measured distribution
        x0 = measured_norm.copy()

        # Optimize
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-10, "maxiter": 1000},
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")

        # Extract corrected distribution
        corrected = result.x

        # Clean up numerical artifacts
        corrected[corrected < 1e-10] = 0

        # Rescale if preserving total intensity
        if preserve_total:
            corrected = corrected * total_intensity

        return corrected

    def correct_time_series(
        self,
        intensity_2d: np.ndarray,
        formula: str,
        label_element: str,
        label_atoms: int,
        tbdms: int = 0,
        meox: int = 0,
        me: int = 0,
    ) -> np.ndarray:
        """
        Apply correction to a full chromatographic time series.

        Args:
            intensity_2d: 2D array of shape (n_isotopologues, n_timepoints)
            formula: Base molecular formula
            label_element: Labeled element (typically 'C')
            label_atoms: Number of labeled positions
            tbdms: TBDMS derivatization count
            meox: MeOX derivatization count
            me: Methylation count

        Returns:
            Corrected 2D intensity array
        """
        # Calculate derivative formula
        deriv_formula, elements = self.calculate_derivative_formula(
            formula, tbdms, meox, me
        )

        logger.info(f"Correcting with derivative formula: {deriv_formula}")
        logger.info(
            f"  Total carbons: {elements.get('C', 0)}, Labeled positions: {label_atoms}"
        )

        # Build correction matrix once
        correction_matrix = self.build_correction_matrix(
            deriv_formula, label_element, label_atoms
        )

        logger.debug(f"Correction matrix shape: {correction_matrix.shape}")
        logger.debug(f"Matrix diagonal: {np.diag(correction_matrix)}")

        # Prepare output array
        n_isotopologues, n_timepoints = intensity_2d.shape
        corrected_2d = np.zeros_like(intensity_2d)

        # Apply correction at each time point
        for t in range(n_timepoints):
            measured = intensity_2d[:, t]

            # Skip if no signal
            if np.sum(measured) < 1e-10:
                corrected_2d[:, t] = 0
                continue

            # Apply correction
            try:
                corrected = self.correct_isotopologue_distribution(
                    measured, correction_matrix, preserve_total=True
                )
                corrected_2d[:, t] = corrected
            except Exception as e:
                logger.warning(f"Correction failed at time point {t}: {e}")
                corrected_2d[:, t] = measured  # Fall back to uncorrected

        return corrected_2d


def correct_eic_data(
    eic_intensity: np.ndarray,
    compound_formula: str,
    label_atoms: int,
    label_element: str = "C",
    tbdms: int = 0,
    meox: int = 0,
    me: int = 0,
) -> np.ndarray:
    """
    Convenience function to correct EIC data for natural abundance.

    Args:
        eic_intensity: 2D intensity array (n_isotopologues, n_timepoints)
        compound_formula: Molecular formula
        label_atoms: Number of labeled positions
        label_element: Labeled element (default 'C')
        tbdms: TBDMS groups
        meox: MeOX groups
        me: Methylations

    Returns:
        Corrected intensity array
    """
    corrector = NaturalAbundanceCorrector()
    return corrector.correct_time_series(
        eic_intensity, compound_formula, label_element, label_atoms, tbdms, meox, me
    )
