"""
Documentation viewer dialog for displaying markdown files with formatting.
"""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

try:
    import markdown

    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

logger = logging.getLogger(__name__)


class DocumentationViewer(QDialog):
    """Dialog for viewing markdown documentation files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MANIC Documentation")
        self.setModal(True)
        self.resize(900, 700)

        # Remove window border/frame for cleaner look
        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Text display area with scroll and clickable links
        self.text_display = QTextBrowser()

        # Disable automatic external link opening so we can handle logic ourselves
        self.text_display.setOpenExternalLinks(False)
        self.text_display.anchorClicked.connect(self._handle_anchor_click)

        # Remove border from text display
        self.text_display.setStyleSheet("QTextEdit { border: none; }")

        # Use platform-appropriate font with larger size
        if sys.platform == "win32":
            display_font = QFont("Arial", 11)
        elif sys.platform == "darwin":
            display_font = QFont("Helvetica", 11)
        else:
            display_font = QFont("DejaVu Sans", 11)
        self.text_display.setFont(display_font)

        # Enable word wrap
        self.text_display.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)

        layout.addWidget(self.text_display)

        # Button layout
        button_layout = QHBoxLayout()

        # Close button
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addStretch()  # Push button to the right
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _handle_anchor_click(self, url: QUrl):
        """
        Handle link clicks in the text browser.

        - Opens web links in system browser.
        - Loads relative .md files in this viewer.
        """
        scheme = url.scheme()

        # Case 1: Web links -> Open in system browser
        if scheme in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return

        # Case 2: Documentation links (.md) -> Load internally
        path = url.toString()
        # Strip anchor if present (e.g. 'file.md#section') to get filename
        file_target = path.split("#")[0]

        if file_target.endswith(".md"):
            # Extract just the filename (e.g. "Reference_Mass_Tolerance.md")
            # This handles both "file.md" and "docs/file.md" links
            filename = Path(file_target).name

            from manic.utils.paths import docs_path

            target_path = Path(docs_path(filename))

            if target_path.exists():
                self.load_markdown_file(target_path)
            else:
                logger.warning(f"Documentation link target not found: {target_path}")
                # Optional: You could show a small status message here
        else:
            # Let QTextBrowser handle internal anchors (scrolling)
            self.text_display.setSource(url)

    def load_markdown_file(self, file_path: Path) -> bool:
        """
        Load and display a markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not file_path.exists():
                self.text_display.setPlainText(f"File not found: {file_path}")
                return False

            # Read the markdown content
            content = file_path.read_text(encoding="utf-8")

            # Ensure proper line endings for markdown parsing
            # This fixes issues with lists not being recognized after previous lines
            content = content.replace("\r\n", "\n").replace("\r", "\n")

            # Ensure blank lines before lists for proper parsing
            import re

            # Add blank line before lists that come after non-list content
            content = re.sub(r"([^\n])\n([-*]|\d+\.)\s", r"\1\n\n\2 ", content)

            if HAS_MARKDOWN:
                # Convert markdown to HTML with proper extensions for lists and formatting
                md = markdown.Markdown(
                    extensions=[
                        "markdown.extensions.extra",  # Includes tables, fenced code, and more
                        "markdown.extensions.codehilite",
                        "markdown.extensions.sane_lists",  # Better list handling
                        "markdown.extensions.nl2br",  # Convert newlines to <br> tags where appropriate
                        # Removed 'markdown.extensions.toc' to prevent auto-generated TOC
                    ]
                )
                html_content = md.convert(content)

                # Apply GitHub-like CSS styling
                styled_html = f"""
                <html>
                <head>
                <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
                    font-size: 16px;
                    line-height: 1.5;
                    color: #1f2328;
                    background-color: #ffffff;
                    padding: 20px;
                    max-width: 980px;
                    margin: 0 auto;
                }}
                h1 {{ 
                    padding-bottom: .3em;
                    font-size: 2em;
                    font-weight: 600;
                    border-bottom: 1px solid #d1d9e0;
                    margin-top: 24px;
                    margin-bottom: 16px;
                    line-height: 1.25;
                }}
                h2 {{ 
                    padding-bottom: .3em;
                    font-size: 1.5em;
                    font-weight: 600;
                    border-bottom: 1px solid #d1d9e0;
                    margin-top: 24px;
                    margin-bottom: 16px;
                    line-height: 1.25;
                }}
                h3 {{ 
                    font-size: 1.25em;
                    font-weight: 600;
                    margin-top: 24px;
                    margin-bottom: 16px;
                    line-height: 1.25;
                }}
                h4 {{ 
                    font-size: 1em;
                    font-weight: 600;
                    margin-top: 24px;
                    margin-bottom: 16px;
                    line-height: 1.25;
                }}
                p {{ 
                    margin-top: 0;
                    margin-bottom: 16px;
                }}
                a {{ 
                    color: #0969da;
                    text-decoration: none;
                }}
                a:hover {{ 
                    text-decoration: underline;
                }}
                code {{ 
                    padding: .2em .4em;
                    margin: 0;
                    font-size: 85%;
                    white-space: break-spaces;
                    background-color: rgba(175,184,193,0.2);
                    border-radius: 6px;
                    font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, Courier, monospace;
                }}
                pre {{ 
                    padding: 16px;
                    overflow: auto;
                    font-size: 85%;
                    line-height: 1.45;
                    color: #1f2328;
                    background-color: #f6f8fa;
                    border-radius: 6px;
                    margin-top: 0;
                    margin-bottom: 16px;
                }}
                pre code {{ 
                    padding: 0;
                    margin: 0;
                    background-color: transparent;
                    border: 0;
                    font-size: 100%;
                }}
                blockquote {{ 
                    padding: 0 1em;
                    color: #59636e;
                    border-left: .25em solid #d1d9e0;
                    margin: 0 0 16px 0;
                }}
                ul, ol {{ 
                    margin-top: 0;
                    margin-bottom: 16px;
                    padding-left: 2em;
                }}
                ul ul, ul ol, ol ul, ol ol {{
                    margin-top: 0;
                    margin-bottom: 0;
                }}
                li {{ 
                    margin-top: .25em;
                }}
                li + li {{
                    margin-top: .25em;
                }}
                li > p {{
                    margin-top: 16px;
                }}
                table {{ 
                    display: block;
                    width: max-content;
                    max-width: 100%;
                    overflow: auto;
                    border-spacing: 0;
                    border-collapse: collapse;
                    margin-top: 0;
                    margin-bottom: 16px;
                }}
                table th {{ 
                    font-weight: 600;
                    padding: 6px 13px;
                    border: 1px solid #d1d9e0;
                    background-color: #f6f8fa;
                }}
                table td {{ 
                    padding: 6px 13px;
                    border: 1px solid #d1d9e0;
                }}
                table tr {{
                    background-color: #ffffff;
                    border-top: 1px solid #d1d9e0;
                }}
                table tr:nth-child(2n) {{
                    background-color: #f6f8fa;
                }}
                hr {{ 
                    height: 1px;
                    padding: 0;
                    margin: 24px 0;
                    background-color: transparent;
                    border: 0;
                    border-bottom: 1px solid #d1d9e0;
                }}
                strong {{ 
                    font-weight: 600;
                }}
                em {{ 
                    font-style: italic;
                }}
                </style>
                </head>
                <body>
                {html_content}
                </body>
                </html>
                """

                self.text_display.setHtml(styled_html)
            else:
                # Fallback to plain text if markdown library not available
                self.text_display.setPlainText(content)

            # Set window title to include file name
            self.setWindowTitle(
                f"MANIC Documentation - {file_path.stem.replace('_', ' ').title()}"
            )

            return True

        except Exception as e:
            logger.error(f"Error loading markdown file: {e}")
            self.text_display.setPlainText(f"Error loading file: {str(e)}")
            return False

    def show_documentation(self, doc_name: str) -> None:
        """
        Show a specific documentation file.

        Args:
            doc_name: Name of the documentation file (without .md extension)
        """
        from manic.utils.paths import docs_path

        # Corrected usage of docs_path helper
        file_path = Path(docs_path(f"{doc_name}.md"))

        if self.load_markdown_file(file_path):
            self.exec()


def show_documentation_file(parent, file_path: Path) -> None:
    """
    Convenience function to show a documentation file in a dialog.

    Args:
        parent: Parent widget for the dialog
        file_path: Path to the markdown file to display
    """
    viewer = DocumentationViewer(parent)
    if viewer.load_markdown_file(file_path):
        viewer.exec()

