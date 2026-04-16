"""Test package bootstrap for headless Qt environments."""

import os

from PyQt5.QtCore import QCoreApplication, Qt


# Package builders run without an X server, so use the minimal backend and
# software OpenGL for compatibility with older Qt stacks.
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

# QtWebEngine requires this attribute before any Qt application is created.
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
