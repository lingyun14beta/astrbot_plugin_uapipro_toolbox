import aiohttp
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/network/whois"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    域名 WHOIS 查询模块 - 全量数据集成版
    """
    usage_hint = (
        "🌐 WHOIS 指令规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u whois <域名>\n"
        "示例：/u whois google.com"
    )

    domain = arg_str.strip().lower()
    if not domain:
        return False, "", usage_hint

    if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$", domain):
        safe_domain = domain[:30]
        return False, "", f"❌ 域名格式错误：{safe_domain}\n\n{usage_hint}"

    params = {"domain": domain, "format": "json"}
    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=12) as resp:
            data = await resp.json(content_type=None) if resp.status == 200 else {}
            if resp.status != 200:
                api_msg = str(data.get("message", "查询失败"))[:100]
                return False, "", f"❌ 接口请求失败: {api_msg}"

            whois_raw = data.get("whois", "")
            raw_text = str(whois_raw) if isinstance(whois_raw, str) else ""

            # 辅助函数：正则提取
            def get_v(pattern, text):
                m = re.search(pattern, text, re.I)
                return m.group(1).strip() if m else None

            # 1. 基础信息提取
            if isinstance(whois_info := data.get("whois"), dict):
                d = whois_info.get("domain", {})
                r = whois_info.get("registrar", {})
                reg = whois_info.get("registrant", {})
                
                res_domain = d.get("domain", domain).upper()
                res_id = d.get("id") or get_v(r"Registry Domain ID:\s*(.*)", raw_text) or "--"
                res_org = reg.get("organization") or get_v(r"Registrant Organization:\s*(.*)", raw_text) or "隐身或未提供"
                res_country = reg.get("country") or get_v(r"Registrant Country:\s*(.*)", raw_text) or "--"
                
                res_registrar = r.get("name") or get_v(r"Registrar:\s*(.*)", raw_text) or "--"
                res_iana = r.get("id") or get_v(r"Registrar IANA ID:\s*(.*)", raw_text) or "--"
                res_reg_url = r.get("referral_url") or get_v(r"Registrar URL:\s*(.*)", raw_text) or "--"
                res_email = r.get("email") or get_v(r"Abuse Contact Email:\s*(.*)", raw_text) or "--"
                res_phone = r.get("phone") or get_v(r"Abuse Contact Phone:\s*(.*)", raw_text) or "--"
                
                res_created = str(d.get("created_date", ""))[:10] or get_v(r"Creation Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                res_expired = str(d.get("expiration_date", ""))[:10] or get_v(r"Expiry Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                res_updated = str(d.get("updated_date", ""))[:10] or get_v(r"Updated Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                
                res_ns = d.get("name_servers") or re.findall(r"Name Server:\s*(\S+)", raw_text, re.I)
                res_status = d.get("status") or re.findall(r"Domain Status:\s*(\S+)", raw_text, re.I)
                res_sec = get_v(r"DNSSEC:\s*(.*)", raw_text) or "未知"
            else:
                # 纯文本 fallback 逻辑
                res_domain = domain.upper()
                res_id = get_v(r"Registry Domain ID:\s*(.*)", raw_text) or "--"
                res_org = get_v(r"Registrant Organization:\s*(.*)", raw_text) or "未公开"
                res_country = get_v(r"Registrant Country:\s*(.*)", raw_text) or "--"
                res_registrar = get_v(r"Registrar:\s*(.*)", raw_text) or "--"
                res_iana = get_v(r"Registrar IANA ID:\s*(.*)", raw_text) or "--"
                res_reg_url = get_v(r"Registrar URL:\s*(.*)", raw_text) or "--"
                res_email = get_v(r"Abuse Contact Email:\s*(.*)", raw_text) or get_v(r"Registrar Abuse Contact Email:\s*(.*)", raw_text) or "--"
                res_phone = get_v(r"Abuse Contact Phone:\s*(.*)", raw_text) or get_v(r"Registrar Abuse Contact Phone:\s*(.*)", raw_text) or "--"
                res_created = get_v(r"Creation Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                res_expired = get_v(r"Expiry Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or get_v(r"Expiration Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                res_updated = get_v(r"Updated Date:\s*(\d{4}-\d{2}-\d{2})", raw_text) or "--"
                res_ns = re.findall(r"Name Server:\s*(\S+)", raw_text, re.I)
                res_status = re.findall(r"Domain Status:\s*(\S+)", raw_text, re.I)
                res_sec = get_v(r"DNSSEC:\s*(.*)", raw_text) or "未知"

            # 组装展示字段
            fields = [
                ("域名详情", f"🌐 {res_domain}\n🆔 ID: {res_id}\n🏳️ 注册国家: {res_country}"),
                ("注册人机构", f"👤 {res_org}"),
                ("注册商信息", f"🏢 {res_registrar}\n🔢 IANA ID: {res_iana}\n🔗 {res_reg_url}"),
                ("滥用投诉", f"☎️ {res_phone}\n📧 {res_email}"),
                ("关键日期", f"📅 注册: {res_created}\n⌛ 到期: {res_expired}\n🔄 更新: {res_updated}"),
                ("网络与安全", f"📡 DNS: {', '.join(sorted(list(set(res_ns)))[:4])}\n🔐 DNSSEC: {res_sec}")
            ]

            if res_status:
                clean_status = sorted(list(set([s.split('(')[0].split()[0].strip() for s in res_status])))
                fields.append(("域名状态 (EPP)", "⚖️ " + "\n⚖️ ".join(clean_status[:6])))

            html = render_card(f"{domain} 完整注册档案", "🌐", fields, "#4E73DF")
            return True, html, ""

    except Exception as e:
        logger.warning(f"[UApiPro] WHOIS 查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()