"""由程序自己管理的 OpenGL 纹理，用来显示预览画面与时间轴缩略图。

纹理创建之后一直保留，只在图片内容变化时重新上传，不依赖任何带有过期时间的缓存。
用到的都是 OpenGL 1.1 的函数，直接从 Windows 自带的 opengl32.dll 调用。
"""

from __future__ import annotations

import ctypes

import cv2
import numpy as np
from imgui_bundle import imgui

GL_TEXTURE_2D = 0x0DE1
GL_TEXTURE_BINDING_2D = 0x8069
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_MAG_FILTER = 0x2800
GL_TEXTURE_WRAP_S = 0x2802
GL_TEXTURE_WRAP_T = 0x2803
GL_LINEAR = 0x2601
GL_CLAMP_TO_EDGE = 0x812F
GL_UNPACK_ALIGNMENT = 0x0CF5
GL_RGB = 0x1907
GL_UNSIGNED_BYTE = 0x1401

_gl = ctypes.windll.opengl32
_gl.glGenTextures.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
_gl.glBindTexture.argtypes = [ctypes.c_uint, ctypes.c_uint]
_gl.glGetIntegerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
_gl.glTexParameteri.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
_gl.glPixelStorei.argtypes = [ctypes.c_uint, ctypes.c_int]
_gl.glTexImage2D.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]


class Texture:
    """一张可以重复上传内容的纹理。只能在界面线程里、OpenGL 初始化之后使用。"""

    def __init__(self) -> None:
        self._id = 0

    def upload(self, bgr: np.ndarray) -> None:
        """把一张 BGR 图片上传到纹理。"""
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        height, width = rgb.shape[:2]
        previous = ctypes.c_int(0)
        _gl.glGetIntegerv(GL_TEXTURE_BINDING_2D, ctypes.byref(previous))
        if self._id == 0:
            created = ctypes.c_uint(0)
            _gl.glGenTextures(1, ctypes.byref(created))
            self._id = created.value
            _gl.glBindTexture(GL_TEXTURE_2D, self._id)
            _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        else:
            _gl.glBindTexture(GL_TEXTURE_2D, self._id)
        _gl.glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        _gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE,
                         rgb.ctypes.data_as(ctypes.c_void_p))
        _gl.glBindTexture(GL_TEXTURE_2D, previous.value)

    def draw(self, width: float, height: float) -> None:
        imgui.image(imgui.ImTextureRef(self._id), imgui.ImVec2(width, height))
