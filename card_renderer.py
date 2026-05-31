import html
import re
from datetime import datetime

IMAGE_WHITELIST = [
    r"textures\.minecraft\.net",
    r"uapis\.cn",
    r".+\.qlogo\.cn",
    r"q\.qlogo\.cn"
]


def render_card(title: str, icon: str, fields: list[tuple[str, str]], accent_color: str = "#5B9BD5", footer: str = "Powered by UApiPro") -> str:
    """
    渲染 HTML 卡片
    优化：全白背景融合设计，加深投影效果，消除视觉留白感
    """
    safe_title = html.escape(title)
    safe_icon = html.escape(icon)
    safe_footer = html.escape(footer)
    safe_accent_color = html.escape(accent_color)
    
    sections_html = ""
    whitelist_regex = "|".join(IMAGE_WHITELIST)

    for label, value in fields:
        s_label = html.escape(str(label))
        val_str = str(value)

        if val_str.startswith("data:image/") and ";base64," in val_str:
            s_value = f'<div class="img-box"><img src="{val_str}"></div>'
        elif re.match(rf'^https?://({whitelist_regex})/', val_str):
            s_value = f'<div class="img-box"><img src="{val_str}" referrerpolicy="no-referrer"></div>'
        else:
            s_value = html.escape(val_str).replace("\n", "<br>")

        sections_html += f"""
        <div class="item">
            <div class="item-label">
                <div class="dot" style="background:{safe_accent_color};"></div>
                {s_label}
            </div>
            <div class="item-value">{s_value}</div>
        </div>
        """

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=700">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            
            html {{ background: #FFFFFF; display: table; width: 100%; }}

            body {{ 
                display: table-cell;
                width: 700px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif; 
                text-align: center;
            }}
            
            .card {{
                width: 700px;
                background: #FFFFFF;
                border-radius: 45px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.08), 0 5px 15px rgba(0,0,0,0.04);
                overflow: hidden;
                border: 1px solid rgba(0,0,0,0.05);
                text-align: left;
            }}

            .header {{
                padding: 50px 45px;
                display: flex;
                align-items: center;
                gap: 20px;
                border-bottom: 2px solid #F5F5F7;
            }}

            .header-icon-box {{
                width: 90px; height: 90px;
                background: #F5F5F7;
                border-radius: 26px;
                display: flex; align-items: center; justify-content: center;
                font-size: 55px;
                flex-shrink: 0;
            }}

            .header-text-box {{ flex: 1; min-width: 0; }}

            .header-title {{
                font-size: 36px; font-weight: 800; color: #1D1D1F; line-height: 1.3;
                overflow-wrap: break-word;
                word-break: break-word;
            }}

            .content {{ padding: 35px 45px 45px 45px; }}

            .item {{ margin-bottom: 35px; }}
            .item:last-child {{ margin-bottom: 0; }}

            .item-label {{
                font-size: 21px; font-weight: 600; color: #86868B;
                margin-bottom: 12px;
                display: flex; align-items: center; gap: 10px;
                text-transform: uppercase; letter-spacing: 0.8px;
            }}

            .dot {{ width: 6px; height: 24px; border-radius: 4px; }}

            .item-value {{
                font-size: 30px; font-weight: 500; color: #1D1D1F; line-height: 1.5;
                overflow-wrap: break-word;
                word-break: break-word;
            }}

            .img-box {{
                margin-top: 15px; border-radius: 20px; overflow: hidden;
                display: inline-block; max-width: 100%;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}

            .img-box img {{ max-width: 100%; display: block; }}

            .footer {{
                padding: 30px 45px; background: #FBFBFC;
                display: flex; justify-content: space-between;
                font-size: 19px; color: #AEAEB2; font-weight: 500;
                border-top: 1px solid #F5F5F7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="header-icon-box">{safe_icon}</div>
                <div class="header-text-box"><div class="header-title">{safe_title}</div></div>
            </div>
            <div class="main"><div class="content">{sections_html}</div></div>
            <div class="footer">
                <span>{safe_footer}</span>
                <span>{now}</span>
            </div>
        </div>
    </body>
    </html>
    """
