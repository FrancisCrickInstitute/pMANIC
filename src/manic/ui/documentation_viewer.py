"""
Documentation viewer dialog for displaying markdown files with formatting.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QPushButton,
    QHBoxLayout,
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
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Text display area with scroll and clickable links
        self.text_display = QTextBrowser()
        self.text_display.setOpenExternalLinks(True)
        
        # Remove border from text display
        self.text_display.setStyleSheet("QTextEdit { border: none; }")
        
        # Use platform-appropriate font with larger size
        if sys.platform == "win32":
            display_font = QFont("Arial", 12)
        elif sys.platform == "darwin": 
            display_font = QFont("Helvetica", 12)
        else:
            display_font = QFont("DejaVu Sans", 12)
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
            content = file_path.read_text(encoding='utf-8')
            
            if HAS_MARKDOWN:
                # Convert markdown to HTML with extensions for better formatting and TOC
                md = markdown.Markdown(extensions=[
                    'markdown.extensions.tables',
                    'markdown.extensions.fenced_code',
                    'markdown.extensions.codehilite',
                    'markdown.extensions.toc'
                ])
                html_content = md.convert(content)
                toc_html = md.toc or ""
                
                # Apply elegant CSS for clean, readable documentation
                # Build final HTML with optional TOC
                styled_html = f"""
                <html>
                <head>
                <style>
                body {{ 
                    background-color: white;
                    color: #333;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    font-size: 15px;
                    line-height: 1.7;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 40px;
                }}
                a {{ color: #0d6efd; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                h1 {{ 
                    color: #1a1a1a;
                    font-size: 32px;
                    font-weight: 700;
                    margin: 0 0 24px 0;
                    padding-bottom: 12px;
                    border-bottom: 3px solid #e1e4e8;
                }}
                h2 {{ 
                    color: #24292e;
                    font-size: 24px;
                    font-weight: 600;
                    margin: 36px 0 16px 0;
                    padding-bottom: 8px;
                    border-bottom: 1px solid #e1e4e8;
                }}
                h3 {{ 
                    color: #24292e;
                    font-size: 20px;
                    font-weight: 600;
                    margin: 28px 0 12px 0;
                }}
                h4 {{ 
                    color: #24292e;
                    font-size: 16px;
                    font-weight: 600;
                    margin: 24px 0 8px 0;
                }}
                h5, h6 {{ 
                    color: #24292e;
                    font-size: 14px;
                    font-weight: 600;
                    margin: 20px 0 8px 0;
                }}
                p {{ 
                    color: #333;
                    margin: 0 0 16px 0;
                }}
                code {{ 
                    background-color: #f6f8fa;
                    color: #24292e;
                    padding: 3px 6px;
                    border-radius: 6px;
                    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Monaco, "Courier New", monospace;
                    font-size: 85%;
                    border: 1px solid #e1e4e8;
                }}
                pre {{ 
                    background-color: #f6f8fa;
                    color: #24292e;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #e1e4e8;
                    overflow-x: auto;
                    font-size: 14px;
                    line-height: 1.45;
                    margin: 16px 0;
                }}
                pre code {{
                    background-color: transparent;
                    color: inherit;
                    padding: 0;
                    border: none;
                    font-size: inherit;
                }}
                table {{ 
                    border-collapse: collapse; 
                    width: 100%;
                    margin: 20px 0;
                    background-color: white;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    overflow: hidden;
                }}
                th {{ 
                    background-color: #f6f8fa;
                    color: #24292e;
                    font-weight: 600;
                    padding: 12px 16px;
                    text-align: left;
                    border-bottom: 1px solid #d0d7de;
                }}
                td {{ 
                    padding: 12px 16px;
                    border-bottom: 1px solid #d0d7de;
                    color: #333;
                }}
                tr:last-child td {{
                    border-bottom: none;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                blockquote {{
                    border-left: 4px solid #d0d7de;
                    margin: 16px 0;
                    padding: 0 16px;
                    color: #656d76;
                    background-color: #f6f8fa;
                    border-radius: 0 6px 6px 0;
                }}
                ul, ol {{ 
                    margin: 16px 0;
                    padding-left: 32px;
                    color: #333;
                }}
                li {{ 
                    margin: 8px 0;
                    line-height: 1.6;
                }}
                strong {{ 
                    color: #24292e;
                    font-weight: 600;
                }}
                em {{ 
                    color: #333;
                    font-style: italic;
                }}
                hr {{
                    border: none;
                    height: 1px;
                    background-color: #e1e4e8;
                    margin: 32px 0;
                }}
                img {{ max-width: 100%; height: auto; display: block; margin: 16px auto; }}
                /* Table of contents styling */
                .toc {{
                    background: #ffffff;
                    border: 1px solid #e1e4e8;
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin: 0 0 24px 0;
                }}
                .toc ul {{ margin: 0; padding-left: 20px; }}
                .toc a {{ color: #0d6efd; text-decoration: none; }}
                .toc a:hover {{ text-decoration: underline; }}
                /* Special styling for warnings/notes */
                p:has(strong:first-child) {{
                    background-color: #fff8dc;
                    border-left: 4px solid #f0ad4e;
                    padding: 12px 16px;
                    margin: 16px 0;
                    border-radius: 0 6px 6px 0;
                }}
                </style>
                </head>
                <body>
                {('<h2>On this page</h2>' + toc_html) if toc_html.strip() else ''}
                {html_content}
                </body>
                </html>
                """
                
                self.text_display.setHtml(styled_html)
            else:
                # Fallback to plain text if markdown is not available
                self.text_display.setPlainText(content)
                logger.warning("Markdown library not available, displaying as plain text")
                
            # Update window title with filename
            self.setWindowTitle(f"MANIC Documentation - {file_path.name}")
            
            return True
            
        except Exception as e:
            error_msg = f"Error loading {file_path}: {str(e)}"
            logger.error(error_msg)
            self.text_display.setPlainText(error_msg)
            return False


def show_documentation_file(parent, file_path: Path):
    """
    Convenience function to show a documentation file in a dialog.
    
    Args:
        parent: Parent widget
        file_path: Path to the markdown file to display
    """
    dialog = DocumentationViewer(parent)
    if dialog.load_markdown_file(file_path):
        dialog.exec()
    else:
        logger.error(f"Failed to load documentation file: {file_path}")
