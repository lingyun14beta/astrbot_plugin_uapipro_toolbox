import html, re
from datetime import datetime

def render_card(title: str, icon: str, fields: list[tuple[str, str]], accent_color: str = "#5B9BD5", footer: str = "Powered by UApiPro") -> str:
    # 基础内容强制转义
    safe_title = html.escape(title)
    safe_icon = html.escape(icon)
    safe_footer = html.escape(footer)
    safe_accent_color = html.escape(accent_color)
    
    sections_html = ""
    for label, value in fields:
        s_label = html.escape(str(label))
        val_str = str(value)

        # 核心修复：Favicon 安全处理
        # 仅当内容符合 Base64 图片格式或严格的 https 格式时，才生成 img 标签
        if val_str.startswith("data:image/") and ";base64," in val_str:
            # Base64 图标路径：受控生成
            s_value = f'<img src="{val_str}" style="width:100px; height:100px; border-radius:12px;">'
        elif val_str.startswith("https://") and re.match(r'^https://[a-zA-Z0-9./\-_]+$', val_str):
            # HTTPS URL 路径：受控生成，带隐私保护
            s_value = f'<img src="{val_str}" referrerpolicy="no-referrer" style="width:100px; height:100px; border-radius:12px;">'
        else:
            # 普通文本：强制转义并处理换行
            s_value = html.escape(val_str).replace("\n", "<br>")

        sections_html += f"""
        <div class="section">
            <div class="section-title">
                <div class="dot" style="background:{safe_accent_color}"></div>
                {s_label}
            </div>
            <div class="section-content">{s_value}</div>
        </div>
        """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ width: 100%; background: #F4F7F9; font-family: sans-serif; padding: 40px; }}
            .container {{ width: 100%; background: white; border-radius: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, {safe_accent_color} 0%, #FFFFFF 200%); padding: 70px 60px; text-align: center; color: white; }}
            .header-icon {{ font-size: 100px; margin-bottom: 20px; display: block; }}
            .header-title {{ font-size: 60px; font-weight: bold; letter-spacing: 4px; color: white; text-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .main {{ padding: 40px 60px; }}
            .section {{ background: white; border: 3px solid #EDF2F7; border-radius: 30px; padding: 45px; margin-bottom: 35px; }}
            .section-title {{ font-size: 32px; color: #94A3B8; font-weight: 600; margin-bottom: 15px; display: flex; align-items: center; gap: 15px; }}
            .dot {{ width: 12px; height: 36px; border-radius: 6px; }}
            .section-content {{ font-size: 46px; color: #2D3748; line-height: 1.6; font-weight: 500; word-wrap: break-word; }}
            .footer {{ padding: 40px 60px; background: #F8FAFC; border-top: 3px solid #EDF2F7; display: flex; justify-content: space-between; align-items: center; }}
            .footer-text {{ color: #A0AEC0; font-size: 28px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="header-icon">{safe_icon}</span>
                <span class="header-title">{safe_title}</span>
            </div>
            <div class="main">{sections_html}</div>
            <div class="footer">
                <span class="footer-text">{safe_footer}</span>
                <span class="footer-text">{now}</span>
            </div>
        </div>
    </body>
    </html>
    """