"""
 @file
 @brief Shared UI text sanitizers for platform-specific paint issues
"""

import platform


def sanitize_ui_text(text):
    """Normalize text before handing it to Qt widgets on platforms with paint issues.

    On current macOS/Qt builds, some emoji glyphs can crash native text painting
    inside common widgets such as QLabel and QPushButton. Replace those glyphs
    with safe ASCII fallbacks before the text reaches the painter.
    """
    if text is None:
        return ""

    value = str(text)
    if platform.system() != "Darwin":
        return value

    sanitized = []
    for ch in value:
        codepoint = ord(ch)
        if codepoint in (0xFE0E, 0xFE0F):
            continue
        if codepoint > 0xFFFF:
            sanitized.append("?")
            continue
        sanitized.append(ch)
    return "".join(sanitized)
