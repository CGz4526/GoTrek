"""OCR 模块：使用 PaddleOCR 3.x 从图片提取文字。

懒加载 PaddleOCR 实例（首次调用时初始化，避免启动卡顿）。

注意：PaddleOCR 3.x 与 2.x API 不兼容：
- 创建实例：不再接受 use_angle_cls/show_log，使用 enable_mkldnn=False
- 调用：使用 predict() 替代 ocr()
- 结果：使用 rec_texts 字段替代遍历 result[0]
- 必须禁用 oneDNN（FLAGS_use_mkldnn=0），否则 paddlepaddle 3.3+ 会抛
  NotImplementedError: ConvertPirAttribute2RuntimeAttribute
"""

import os

# 必须在导入 paddle 前设置，禁用 oneDNN 规避 paddlepaddle 3.3+ 的兼容性问题
os.environ.setdefault('FLAGS_use_mkldnn', '0')

_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        # PaddleOCR 3.x：lang='ch' 中文，enable_mkldnn=False 规避 oneDNN 错误
        _ocr_instance = PaddleOCR(lang='ch', enable_mkldnn=False)
    return _ocr_instance


def _parse_result(result) -> str:
    """从 PaddleOCR 3.x 的 predict() 结果中提取文本。

    结果是 OCRResult 列表，每个元素含 rec_texts 字段（识别出的文本行列表）。
    """
    lines = []
    if not result:
        return ""
    for r in result:
        # OCRResult 支持字典式访问和属性访问
        texts = None
        if hasattr(r, 'rec_texts'):
            texts = r.rec_texts
        elif isinstance(r, dict) and 'rec_texts' in r:
            texts = r['rec_texts']
        if texts:
            for t in texts:
                if t and str(t).strip():
                    lines.append(str(t).strip())
    return "\n".join(lines)


def extract_text_from_image(image_path: str) -> str:
    """从图片提取文字，返回拼接后的纯文本。

    Args:
        image_path: 图片文件路径

    Returns:
        提取的文字内容，按行拼接
    """
    # 不吞异常：让错误冒泡到 API 层，前端能看到具体原因而非模糊的"未识别到文字"
    ocr = _get_ocr()
    result = ocr.predict(image_path)
    return _parse_result(result)


def extract_text_from_bytes(image_bytes: bytes) -> str:
    """从图片字节流提取文字。

    Args:
        image_bytes: 图片二进制数据

    Returns:
        提取的文字内容
    """
    import tempfile
    import os
    # 写入临时文件（PaddleOCR 需要文件路径）
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name
    try:
        return extract_text_from_image(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
