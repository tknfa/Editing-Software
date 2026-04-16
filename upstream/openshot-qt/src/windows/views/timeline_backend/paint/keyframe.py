"""
 @file
 @brief Painter for clip and transition keyframes.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen

from .base import BasePainter


class KeyframePainter(BasePainter):
    def update_theme(self):
        fill = self.w.theme.keyframe_fill
        border = self.w.theme.keyframe_border
        base_color = QColor("#4d7bff")
        if fill.isValid():
            base_color = QColor(fill)
        self.fill = base_color
        border_color = QColor("#ffffff")
        if border.isValid():
            border_color = QColor(border)
        self.border = border_color
        self.pen = QPen(self.border, 1.2)
        self.pen.setCosmetic(True)
        self.inactive_opacity = getattr(self.w.theme, "keyframe_inactive_opacity", 0.5)
        self.size = max(1, int(getattr(self.w.theme, "keyframe_size", 10) or 10))

    def paint(self, painter: QPainter):
        markers = getattr(self.w, "_keyframe_markers", [])
        if not markers:
            return

        active_marker = getattr(self.w, "_active_keyframe_marker", None)
        active_key = active_marker.get("key") if isinstance(active_marker, dict) else None
        drag = getattr(self.w, "_dragging_keyframe", None)
        drag_key = drag.get("key") if isinstance(drag, dict) else None
        hover_key = getattr(self.w, "_hover_keyframe_key", None)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen)
        for marker in markers:
            rect = marker.get("rect")
            if not isinstance(rect, QRectF) or rect.isNull():
                continue
            is_retime = (
                marker.get("property_key") == "time"
                and getattr(self.w, "isRetimePropertyFilterActive", lambda: False)()
            )
            marker_key = marker.get("key")
            is_focus = marker_key in (active_key, drag_key, hover_key)
            draw_rect = QRectF(rect)
            if is_retime:
                draw_rect.adjust(-1.5, -1.5, 1.5, 1.5)
            if is_focus:
                glow_rect = QRectF(draw_rect)
                glow_rect.adjust(-4.0, -4.0, 4.0, 4.0)
                glow_color = QColor("#ffffff")
                glow_color.setAlpha(70 if is_retime else 50)
                painter.setOpacity(1.0)
                painter.setPen(Qt.NoPen)
                painter.setBrush(glow_color)
                painter.drawEllipse(glow_rect)
            opacity = 1.0 if marker.get("selected") else self.inactive_opacity
            if marker.get("dimmed"):
                opacity *= 0.5
            painter.setOpacity(opacity)
            color = marker.get("color")
            if not isinstance(color, QColor) or not color.isValid():
                color = self.fill
            painter.setBrush(color)
            painter.setPen(self.pen)
            interpolation = marker.get("interpolation", "bezier")
            if interpolation == "linear":
                painter.drawRect(draw_rect)
            elif interpolation == "constant":
                path = QPainterPath()
                center = draw_rect.center()
                path.moveTo(center.x(), draw_rect.top())
                path.lineTo(draw_rect.right(), center.y())
                path.lineTo(center.x(), draw_rect.bottom())
                path.lineTo(draw_rect.left(), center.y())
                path.closeSubpath()
                painter.drawPath(path)
            else:
                painter.drawEllipse(draw_rect)
        painter.restore()
