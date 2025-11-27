"""
Documentation viewer dialog using QWebEngineView for perfect GitHub-style rendering.

This implementation uses QWebEngineView for:
- Perfect GitHub-identical rendering (HTML/CSS/JavaScript support)
- Full MathJax support for LaTeX math equations
- Professional appearance matching the GitHub documentation
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

logger = logging.getLogger(__name__)


class DocumentationPage(QWebEnginePage):
    """
    Custom QWebEnginePage to intercept and handle link navigation.
    
    This allows us to:
    - Open external links (http/https) in the system browser
    - Navigate between internal .md documentation files
    - Handle anchor links (#section) within documents
    - Support combined links (file.md#section)
    """

    def __init__(self, parent=None, navigation_handler=None):
        """
        Initialize the custom page.
        
        Args:
            parent: Parent widget
            navigation_handler: Callback function to handle navigation requests
        """
        super().__init__(parent)
        self.navigation_handler = navigation_handler

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """
        Intercept all navigation requests before they happen.
        
        This method is called before any link navigation occurs. We use it to:
        1. Route external links to system browser
        2. Handle internal .md file navigation
        3. Allow normal anchor navigation within the page
        
        Args:
            url: The QUrl being navigated to
            nav_type: Type of navigation (link click, form submit, etc.)
            is_main_frame: Whether this is the main frame or an iframe
            
        Returns:
            True to allow navigation, False to block it
        """
        # Only intercept main frame navigation (not iframes or sub-resources)
        if is_main_frame and self.navigation_handler:
            # Delegate to our custom handler
            should_proceed = self.navigation_handler(url)
            return should_proceed
        
        # Allow all other navigation (sub-resources, etc.)
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class DocumentationViewer(QDialog):
    """
    Dialog for viewing markdown documentation files with perfect GitHub rendering.
    
    Features:
    - Full GitHub Flavored Markdown support (tables, code blocks, task lists, etc.)
    - MathJax rendering for LaTeX equations ($...$ and $$...$$)
    - Internal link navigation between .md files
    - Anchor link support (#section)
    - External link handling (opens in system browser)
    - GitHub-identical CSS styling
    """

    def __init__(self, parent=None):
        """
        Initialize the documentation viewer dialog.
        
        Args:
            parent: Parent widget (usually MainWindow)
        """
        super().__init__(parent)
        self.setWindowTitle("MANIC Documentation")
        self.setModal(True)
        self.resize(1000, 800)

        # Standard dialog flags with maximize/close buttons
        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        # Store the docs directory path for resolving relative links
        from manic.utils.paths import docs_path
        self.docs_dir = Path(docs_path())
        
        # Track current file for navigation
        self.current_file = None

        self.setup_ui()

    def setup_ui(self):
        """Create the UI layout with web view and close button."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the web engine view for rendering HTML
        self.web_view = QWebEngineView()
        
        # Attach our custom page handler for link interception
        custom_page = DocumentationPage(self.web_view, self._handle_navigation)
        self.web_view.setPage(custom_page)
        
        # Clean white background
        self.web_view.setStyleSheet("background-color: white;")
        
        # Add web view with stretch factor to fill available space
        layout.addWidget(self.web_view, 1)

        # Bottom control bar with Close button (fixed height)
        button_container = QWidget(self)
        button_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(10, 10, 10, 10)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        # Add button container with no stretch
        layout.addWidget(button_container, 0)

    def _handle_navigation(self, url: QUrl) -> bool:
        """
        Handle all navigation requests from the web view.
        
        This method routes different types of links appropriately:
        1. External links (http://, https://, mailto:) -> Open in system browser
        2. Internal .md file links -> Load the new markdown file
        3. Anchor links (#section) -> Allow browser to handle (scroll to section)
        4. Combined links (file.md#section) -> Load file, browser handles anchor
        
        Args:
            url: The QUrl object representing the navigation target
            
        Returns:
            True to allow navigation in the web view, False to block it
        """
        url_string = url.toString()
        scheme = url.scheme()
        
        logger.debug(f"Navigation requested: {url_string} (scheme: {scheme})")
        
        # Handle external web links - open in system default browser
        if scheme in ("http", "https", "mailto"):
            logger.info(f"Opening external link in browser: {url_string}")
            QDesktopServices.openUrl(url)
            return False  # Block navigation in our view
        
        # Handle anchor-only links (just #section) - let browser handle
        if url_string.startswith("#"):
            anchor = url_string[1:]
            logger.debug(f"Allowing anchor navigation: #{anchor}")
            return True  # Allow browser to scroll to anchor
        
        # Handle file:// or relative links to .md files
        if scheme == "file" or not scheme:
            return self._handle_file_navigation(url)
        
        # Default: allow navigation
        logger.debug(f"Allowing default navigation for: {url_string}")
        return True

    def _handle_file_navigation(self, url: QUrl) -> bool:
        """
        Handle file:// protocol links and relative file paths.
        
        Args:
            url: The QUrl to handle
            
        Returns:
            True to allow navigation, False if we handled it manually
        """
        url_string = url.toString()
        
        # Extract path and fragment (anchor)
        if url.scheme() == "file":
            file_path = url.toLocalFile()
            fragment = url.fragment()
        else:
            # Relative URL - resolve it
            if "#" in url_string:
                path_part, fragment = url_string.split("#", 1)
            else:
                path_part = url_string
                fragment = ""
            
            # Resolve relative to current file or docs directory
            if self.current_file:
                file_path = str((self.current_file.parent / path_part).resolve())
            else:
                file_path = str((self.docs_dir / path_part).resolve())
        
        path = Path(file_path)
        logger.debug(f"File navigation: {path} (fragment: {fragment})")
        
        # Check if it's a markdown file
        if path.suffix.lower() == ".md":
            if path.exists():
                logger.info(f"Loading markdown file: {path.name}")
                # Load the new markdown file, passing fragment for anchor scrolling
                self.load_markdown_file(path, fragment)
                return False  # We handled it manually
            else:
                logger.warning(f"Markdown file not found: {path}")
                self._show_error(f"File not found: {path.name}")
                return False
        else:
            # Non-markdown file - open with system default application
            logger.info(f"Opening non-markdown file with system app: {path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return False

    def load_markdown_file(self, file_path: Path, fragment: str = None) -> bool:
        """
        Load and render a markdown file with full GitHub styling and MathJax.
        
        This method:
        1. Reads the markdown file
        2. Converts it to HTML using markdown library with all GitHub extensions
        3. Wraps it in GitHub-style CSS and MathJax configuration
        4. Displays it in the web view
        5. Scrolls to anchor if fragment provided
        
        Args:
            file_path: Path object pointing to the .md file
            fragment: Optional anchor/section to scroll to (e.g., "section-name")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                self._show_error(f"File not found: {file_path}")
                return False

            logger.info(f"Loading markdown file: {file_path}")
            
            # Read the markdown content
            raw_markdown = file_path.read_text(encoding="utf-8")
            
            # Store current file for relative link resolution BEFORE loading HTML
            self.current_file = file_path
            
            # Convert markdown to HTML
            html_body = self._markdown_to_html(raw_markdown)
            
            # Wrap in complete HTML document with GitHub styling and MathJax
            full_html = self._wrap_with_github_style(html_body)
            
            # Set the HTML content with base URL pointing to docs directory
            # This allows both relative .md links AND _assets/ to resolve correctly
            base_url = QUrl.fromLocalFile(str(self.docs_dir) + "/")
            self.web_view.setHtml(full_html, base_url)
            
            # If fragment provided, scroll to it after page loads
            if fragment:
                def scroll_to_anchor(ok):
                    """Scroll to the anchor after page finishes loading."""
                    if ok:
                        logger.debug(f"Scrolling to anchor: {fragment}")
                        # Use JavaScript to scroll to the anchor
                        self.web_view.page().runJavaScript(f"location.hash = '#{fragment}';")
                    # Disconnect after first use
                    try:
                        self.web_view.loadFinished.disconnect(scroll_to_anchor)
                    except:
                        pass
                
                self.web_view.loadFinished.connect(scroll_to_anchor)
            
            # Update window title
            readable_name = file_path.stem.replace("_", " ").title()
            self.setWindowTitle(f"MANIC Documentation - {readable_name}")
            
            logger.info(f"Successfully loaded: {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error loading markdown file: {e}", exc_info=True)
            self._show_error(f"Error loading file: {str(e)}")
            return False

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown text to HTML with full GitHub Flavored Markdown support.
        
        Extensions enabled:
        - extra: Abbreviations, attribute lists, definition lists, etc.
        - fenced_code: Code blocks with ``` syntax
        - codehilite: Syntax highlighting for code blocks
        - tables: GitHub-style tables
        - nl2br: Convert newlines to <br> tags
        - sane_lists: Better list handling
        - toc: Table of contents support
        - md_in_html: Allow markdown inside HTML blocks
        - pymdownx.arithmatex: LaTeX math support for MathJax
        
        Args:
            markdown_text: Raw markdown content
            
        Returns:
            HTML string
        """
        if not HAS_MARKDOWN:
            logger.warning("Markdown library not available, displaying as plain text")
            # Fallback to preformatted text if markdown not available
            escaped_text = markdown_text.replace("<", "&lt;").replace(">", "&gt;")
            return f"<pre>{escaped_text}</pre>"
        
        try:
            # Initialize markdown converter with GitHub-compatible extensions
            md_converter = markdown.Markdown(
                extensions=[
                    "markdown.extensions.extra",        # Tables, footnotes, attr_list, etc.
                    "markdown.extensions.fenced_code",  # ``` code blocks
                    "markdown.extensions.codehilite",   # Syntax highlighting
                    "markdown.extensions.tables",       # Explicit table support
                    "markdown.extensions.nl2br",        # Newline to <br>
                    "markdown.extensions.sane_lists",   # Better list behavior
                    "markdown.extensions.toc",          # Table of contents
                    "markdown.extensions.md_in_html",   # Markdown in HTML blocks
                    "pymdownx.arithmatex",             # LaTeX math support
                ],
                extension_configs={
                    "codehilite": {
                        "css_class": "highlight",
                        "linenums": False,
                    },
                    "pymdownx.arithmatex": {
                        "generic": True,  # Output format compatible with MathJax
                    }
                }
            )
            
            # Convert to HTML
            html = md_converter.convert(markdown_text)
            
            logger.debug(f"Converted {len(markdown_text)} chars of markdown to {len(html)} chars of HTML")
            return html
            
        except Exception as e:
            logger.error(f"Error converting markdown to HTML: {e}", exc_info=True)
            # Fallback to plain text on error
            escaped_text = markdown_text.replace("<", "&lt;").replace(">", "&gt;")
            return f"<pre>Error rendering markdown:\n{str(e)}\n\n{escaped_text}</pre>"

    def _wrap_with_github_style(self, html_body: str) -> str:
        """
        Wrap HTML content in a complete document with GitHub CSS and MathJax.
        
        This creates a complete HTML document with:
        - MathJax 3.x configuration for LaTeX rendering
        - GitHub's exact color scheme and typography
        - Proper heading hierarchy and borders
        - Code block styling with syntax highlighting
        - Table styling with alternating rows
        - Link colors and hover effects
        - Blockquote styling
        - Responsive spacing and padding
        
        Args:
            html_body: The HTML content to wrap
            
        Returns:
            Complete HTML document string
        """
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- MathJax Configuration for LaTeX Math Rendering (Local Bundle) -->
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    processEscapes: true,
    processEnvironments: true
  }},
  startup: {{
    typeset: false  // We'll manually trigger typesetting after load
  }}
}};
</script>
<script defer src="_assets/mathjax/tex-chtml.js"></script>

<style>
    /* Base Body Styling - GitHub's exact font stack and colors */
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
        font-size: 16px;
        line-height: 1.6;
        color: #24292f;
        background-color: #ffffff;
        padding: 32px;
        max-width: 980px;
        margin: 0 auto;
        word-wrap: break-word;
    }}
    
    /* Heading Styles - Matching GitHub exactly */
    h1, h2, h3, h4, h5, h6 {{
        margin-top: 24px;
        margin-bottom: 16px;
        font-weight: 600;
        line-height: 1.25;
        color: #1f2328;
    }}
    
    h1 {{
        font-size: 2em;
        border-bottom: 1px solid #d0d7de;
        padding-bottom: 0.3em;
        margin-top: 0;
    }}
    
    h2 {{
        font-size: 1.5em;
        border-bottom: 1px solid #d0d7de;
        padding-bottom: 0.3em;
    }}
    
    h3 {{
        font-size: 1.25em;
    }}
    
    h4 {{
        font-size: 1em;
    }}
    
    h5 {{
        font-size: 0.875em;
    }}
    
    h6 {{
        font-size: 0.85em;
        color: #57606a;
    }}
    
    /* Paragraph and Text */
    p {{
        margin-top: 0;
        margin-bottom: 16px;
    }}
    
    /* Links - GitHub blue */
    a {{
        color: #0969da;
        text-decoration: none;
    }}
    
    a:hover {{
        text-decoration: underline;
    }}
    
    a:visited {{
        color: #8250df;
    }}
    
    /* Code Blocks and Inline Code */
    pre {{
        padding: 16px;
        overflow: auto;
        font-size: 85%;
        line-height: 1.45;
        background-color: #f6f8fa;
        border-radius: 6px;
        margin-bottom: 16px;
        font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
    }}
    
    code {{
        padding: 0.2em 0.4em;
        margin: 0;
        font-size: 85%;
        background-color: rgba(175,184,193,0.2);
        border-radius: 6px;
        font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
    }}
    
    pre > code {{
        padding: 0;
        margin: 0;
        font-size: 100%;
        word-break: normal;
        white-space: pre;
        background: transparent;
        border: 0;
    }}
    
    /* Blockquotes - GitHub style */
    blockquote {{
        padding: 0 1em;
        color: #57606a;
        border-left: 0.25em solid #d0d7de;
        margin: 0 0 16px 0;
    }}
    
    blockquote > :first-child {{
        margin-top: 0;
    }}
    
    blockquote > :last-child {{
        margin-bottom: 0;
    }}
    
    /* Tables - Critical for documentation */
    table {{
        border-spacing: 0;
        border-collapse: collapse;
        margin-top: 0;
        margin-bottom: 16px;
        width: 100%;
        overflow: auto;
        display: block;
    }}
    
    table th {{
        font-weight: 600;
        padding: 6px 13px;
        border: 1px solid #d0d7de;
        background-color: #f6f8fa;
    }}
    
    table td {{
        padding: 6px 13px;
        border: 1px solid #d0d7de;
    }}
    
    table tr {{
        background-color: #ffffff;
        border-top: 1px solid #d8dee4;
    }}
    
    table tr:nth-child(2n) {{
        background-color: #f6f8fa;
    }}
    
    /* Lists */
    ul, ol {{
        margin-top: 0;
        margin-bottom: 16px;
        padding-left: 2em;
    }}
    
    li {{
        margin-top: 0.25em;
    }}
    
    li > p {{
        margin-top: 16px;
    }}
    
    li + li {{
        margin-top: 0.25em;
    }}
    
    /* Horizontal Rules */
    hr {{
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: #d0d7de;
        border: 0;
    }}
    
    /* Images */
    img {{
        max-width: 100%;
        box-sizing: content-box;
        background-color: #ffffff;
    }}
    
    /* Task Lists */
    input[type="checkbox"] {{
        margin-right: 0.5em;
    }}
    
    /* Strong and Emphasis */
    strong {{
        font-weight: 600;
    }}
    
    em {{
        font-style: italic;
    }}
    
    /* Deleted text (strikethrough) */
    del {{
        text-decoration: line-through;
    }}
    
    /* Math Display Blocks - Center and add spacing */
    .arithmatex {{
        overflow-x: auto;
        margin: 1em 0;
    }}
</style>
</head>
<body>
{html_body}

<!-- Force MathJax to typeset after page loads -->
<script>
(function() {{
  function typesetAndScroll() {{
    if (window.MathJax && MathJax.typesetPromise) {{
      MathJax.typesetPromise().then(function() {{
        // Restore anchor position after typesetting (in case layout shifted)
        if (location.hash) {{ 
          location.hash = location.hash; 
        }}
      }}).catch(function(err) {{ 
        console.error('MathJax typeset error:', err); 
      }});
    }}
  }}
  // Trigger typesetting when page is ready
  if (document.readyState === 'complete') {{ 
    typesetAndScroll(); 
  }} else {{ 
    window.addEventListener('load', typesetAndScroll); 
  }}
}})();
</script>
</body>
</html>"""

    def _show_error(self, message: str):
        """
        Display an error message in the web view.
        
        Args:
            message: Error message to display
        """
        error_html = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                padding: 40px;
                max-width: 600px;
                margin: 0 auto;
            }}
            h2 {{
                color: #d73a49;
                border-bottom: 2px solid #d73a49;
                padding-bottom: 8px;
            }}
            p {{
                color: #586069;
                line-height: 1.6;
            }}
        </style>
        </head>
        <body>
            <h2>Error Loading Documentation</h2>
            <p>{message}</p>
        </body>
        </html>
        """
        self.web_view.setHtml(error_html)


def show_documentation_file(parent, file_path: Path) -> None:
    """
    Convenience function to open the documentation viewer with a specific file.
    
    This creates the viewer dialog, loads the specified markdown file,
    and displays it to the user.
    
    Args:
        parent: Parent widget (usually MainWindow)
        file_path: Path to the markdown file to display
    """
    viewer = DocumentationViewer(parent)
    if viewer.load_markdown_file(file_path):
        viewer.exec()
    else:
        logger.error(f"Failed to load documentation file: {file_path}")
