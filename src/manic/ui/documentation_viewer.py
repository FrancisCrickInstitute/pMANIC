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
    QTextEdit, 
    QPushButton, 
    QHBoxLayout,
    QScrollArea,
    QSizePolicy
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
        
        # Text display area with scroll
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        
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
        self.text_display.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
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
                # Convert markdown to HTML with extensions for better formatting
                html_content = markdown.markdown(
                    content, 
                    extensions=[
                        'markdown.extensions.tables',
                        'markdown.extensions.fenced_code',
                        'markdown.extensions.codehilite',
                        'markdown.extensions.toc'
                    ]
                )
                
                # Apply simple CSS for clean white background with black text
                styled_html = f"""
                <html>
                <head>
                <style>
                body {{ 
                    background-color: white;
                    color: black;
                    font-family: Arial, Helvetica; 
                    font-size: 14px;
                    line-height: 1.6; 
                    margin: 20px;
                }}
                h1, h2, h3, h4, h5, h6 {{ 
                    color: black;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }}
                h1 {{ font-size: 24px; border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
                h2 {{ font-size: 20px; border-bottom: 1px solid #666; padding-bottom: 0.3em; }}
                h3 {{ font-size: 18px; }}
                h4 {{ font-size: 16px; }}
                code {{ 
                    background-color: #f5f5f5; 
                    color: black;
                    padding: 2px 4px; 
                    border-radius: 3px;
                    font-family: Monaco, Consolas, 'DejaVu Sans Mono';
                    font-size: 13px;
                }}
                pre {{ 
                    background-color: #f5f5f5; 
                    color: black;
                    padding: 16px; 
                    border-radius: 6px;
                    border-left: 4px solid #333;
                    overflow-x: auto;
                    font-size: 13px;
                }}
                pre code {{
                    background-color: transparent;
                    color: black;
                    padding: 0;
                    font-family: Monaco, Consolas, 'DejaVu Sans Mono';
                }}
                table {{ 
                    border-collapse: collapse; 
                    width: 100%;
                    margin: 1em 0;
                    background-color: white;
                }}
                th, td {{ 
                    border: 1px solid #333; 
                    padding: 8px; 
                    text-align: left;
                    background-color: white;
                    color: black;
                }}
                th {{ 
                    background-color: #f0f0f0; 
                    font-weight: bold;
                    color: black;
                }}
                blockquote {{
                    border-left: 4px solid #333;
                    margin: 0;
                    padding-left: 16px;
                    color: #333;
                    background-color: white;
                }}
                ul, ol {{ margin: 1em 0; padding-left: 2em; color: black; }}
                li {{ margin: 0.5em 0; color: black; }}
                p {{ color: black; }}
                </style>
                </head>
                <body>
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