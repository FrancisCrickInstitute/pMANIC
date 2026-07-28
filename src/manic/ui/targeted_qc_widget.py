from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TargetedQcWidget(QWidget):
    """Compact live summary of unlabelled identity-supporting checks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Targeted identity QC")
        title.setStyleSheet("font-weight: 600; color: #15324b;")
        layout.addWidget(title)

        self.summary = QLabel("Select a compound and sample.")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(self.summary.textFormat())
        self.summary.setStyleSheet(
            "background-color: #f5f8fa; color: #202124; "
            "border: 1px solid #d7e0e7; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(self.summary)

    def clear(self) -> None:
        self.summary.setText("Select a compound and sample.")

    def update_results(self, compound_name: str, sample_names: list[str], provider) -> None:
        if not compound_name or not sample_names:
            self.clear()
            return

        lines: list[str] = []
        for sample_name in sample_names[:8]:
            try:
                result = provider.assess_unlabelled_identity(
                    sample_name, compound_name
                )
                ratios = ", ".join(
                    (
                        f"Q{ratio.channel.ordinal}={ratio.observed_ratio:.3f}"
                        if ratio.observed_ratio is not None
                        else f"Q{ratio.channel.ordinal}=N/A"
                    )
                    for ratio in result.qualifier_ratios
                )
                rt = (
                    f"{result.observed_rt:.3f} min"
                    if result.observed_rt is not None
                    else "N/A"
                )
                lines.append(
                    f"<b>{escape(sample_name)}</b>: "
                    f"{escape(result.status.value.replace('_', ' ').title())}<br>"
                    f"RT {rt}; {escape(ratios)}"
                )
            except Exception as exc:
                lines.append(
                    f"<b>{escape(sample_name)}</b>: QC unavailable "
                    f"({escape(str(exc))})"
                )

        if len(sample_names) > 8:
            lines.append(f"…and {len(sample_names) - 8} more samples")
        self.summary.setText("<br><br>".join(lines))
