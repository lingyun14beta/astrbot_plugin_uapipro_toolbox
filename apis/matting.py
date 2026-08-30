import aiohttp
import re
from astrbot.api import logger

API_URL = "https://uapis.cn/api/v1/image/matting"

MAX_IMAGE_BYTES = 10 * 1024 * 1024

# 可选值中文名（用于回复文案与本地白名单校验）
MODEL_LABELS = {
    "general": "通用",
    "fast": "轻量快速",
    "portrait": "人像特化",
    "sharp": "高锐利度边缘",
}
OUTPUT_LABELS = {
    "cutout": "透明主体",
    "mask": "灰度蒙版",
    "background": "纯色背景",
}
VALID_FORMATS = {"png", "webp", "jpeg"}


async def fetch(
    image_b64: str,
    token: str,
    settings: dict | None = None,
    session: aiohttp.ClientSession = None,
):
    """
    图片抠图（背景移除）模块。

    Args:
        image_b64: 纯 Base64 编码图片（不带 data:image/...;base64, 前缀）。
        token: UApiPro 接口密钥。
        settings: 面板配置 matting_settings（model/output/background_color/
            out_format/threshold/feather_px），缺省用文档默认值。
        session: 复用的 aiohttp 会话；为 None 时自动创建并关闭。

    Returns:
        (ok, data, err): ok 为 True 时 data 为结果图片 Base64、err 为回复文案；
        失败时 err 为错误提示文本。
    """
    if not image_b64:
        return False, "", "❌ 未获取到图片数据。"

    if len(image_b64) > MAX_IMAGE_BYTES // 3 * 4:
        return False, "", "❌ 图片过大，请发送不超过 10MB 的图片。"

    settings = settings or {}
    model = (settings.get("model") or "general").strip().lower()
    output = (settings.get("output") or "cutout").strip().lower()
    out_format = (settings.get("out_format") or "png").strip().lower()

    # 本地白名单校验：避免无效参数打到接口吃 400
    if model not in MODEL_LABELS:
        return False, "", "❌ 不支持的分割模型，可选：general/fast/portrait/sharp。"
    if output not in OUTPUT_LABELS:
        return False, "", "❌ 不支持的输出形态，可选：cutout/mask/background。"
    if out_format not in VALID_FORMATS:
        return False, "", "❌ 不支持的输出格式，可选：png/webp/jpeg。"

    # jpeg 不支持透明通道，必须 output=background（文档约束，本地预校验给出友好提示）
    if out_format == "jpeg" and output != "background":
        return False, "", (
            "❌ jpeg 不支持透明通道：请将输出形态改为「纯色背景 (background)」"
            "或改用 png/webp。"
        )

    background_color = (settings.get("background_color") or "#438EDB").strip()
    if output == "background" and not re.fullmatch(r"#[0-9a-fA-F]{6}", background_color):
        return False, "", "❌ 底色格式不正确，应为 #RRGGBB（如 #438EDB）。"

    form = aiohttp.FormData()
    form.add_field("image_base64", image_b64)
    form.add_field("model", model)
    form.add_field("output", output)
    form.add_field("out_format", out_format)
    if output == "background":
        form.add_field("background_color", background_color)
    # threshold/feather_px：0/空视为不传（保持原生渐变、不柔化）
    if settings.get("threshold"):
        form.add_field("threshold", str(settings.get("threshold")))
    if settings.get("feather_px"):
        form.add_field("feather_px", str(int(settings.get("feather_px"))))

    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.post(
            API_URL, data=form, timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if not isinstance(data, dict):
                data = {}

            if resp.status == 200:
                result_b64 = data.get("image_base64", "")
                if not result_b64:
                    return False, "", "❌ 抠图服务未返回结果图片，请稍后再试。"
                w, h = data.get("width", "--"), data.get("height", "--")
                ms = data.get("matting_ms", "--")
                out_label = OUTPUT_LABELS.get(output, output)
                model_label = MODEL_LABELS.get(model, model)
                caption = (
                    f"🎨 抠图完成 · {out_label}（{model_label}）\n"
                    f"📐 {w}×{h}px · ⏱ 耗时 {ms}ms"
                )
                return True, result_b64, caption

            api_msg = str(data.get("message", ""))[:150]
            if resp.status == 400:
                return False, "", f"❌ 请求参数错误: {api_msg or '图片数据无效'}"
            if resp.status == 413:
                return False, "", "❌ 图片过大（上限 16MB），请压缩后重试。"
            if resp.status == 415:
                return False, "", "❌ 不支持的图片格式，请发送 JPG/PNG/WebP 等常见格式。"
            if resp.status == 502:
                return False, "", f"❌ 抠图服务失败: {api_msg or '请稍后再试'}"
            if resp.status == 503:
                return False, "", f"❌ 抠图服务繁忙: {api_msg or '请稍后再试'}"
            return False, "", f"❌ 接口请求失败 (HTTP {resp.status}): {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] 抠图请求异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
