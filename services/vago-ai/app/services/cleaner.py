"""
文本清洗模块（Text Cleaner）。

负责对用户导入的原始攻略文本进行多步预处理，
去除 HTML 标签、emoji、广告词汇及多余空白，
输出干净的纯文本供后续分块和向量化使用。
"""

import re

from bs4 import BeautifulSoup

# ─── 广告词正则（小红书/公众号常见推广话术）────────────────────────────────────
_AD_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"关注[我们]?[，,、]?.*?获取更多",
        r"点(个)?赞.*?收藏",
        r"收藏.*?点(个)?赞",
        r"私信[我们]?(领取|获取|回复)",
        r"暗号[:：]?\s*\S+",
        r"扫(描)?码.{0,10}(获取|领取|添加|关注)",
        r"点击(链接|下方|头像).{0,15}(了解|获取|购买)",
        r"限时(优惠|福利|领取).{0,30}",
        r"文末(有|附|留).{0,15}(链接|方式|联系)",
        r"转发(本文|此文|分享).{0,20}",
        r"#\S+",          # Hashtag 标签
        r"@\S+",          # 用户提及
    ]
]

# ─── Unicode Emoji 范围正则 ────────────────────────────────────────────────────
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols etc.
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "]+",
    flags=re.UNICODE,
)


def strip_html(text: str) -> str:
    """
    使用 BeautifulSoup 去除 HTML 标签，保留纯文本内容。

    对于非 HTML 内容，BeautifulSoup 会将其原样返回，不会破坏正常文本。
    使用 lxml 作为解析器以获得更高的解析速度和容错性。
    """
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator="\n")


def strip_emoji(text: str) -> str:
    """
    使用 Unicode 码点范围正则去除常见 emoji 字符。

    覆盖绝大部分 Unicode emoji 区块，包括：
    表情符号、图形符号、交通图标、国旗、附加符号等。
    """
    return _EMOJI_PATTERN.sub("", text)


def strip_ad_phrases(text: str) -> str:
    """
    逐行扫描文本，匹配并删除常见的中文自媒体广告话术。

    匹配范围包括：引流话术、暗号导流、扫码推广、关注引导等。
    """
    for pattern in _AD_PATTERNS:
        text = pattern.sub("", text)
    return text


def normalize_whitespace(text: str) -> str:
    """
    规范化文本空白：
    1. 将制表符和回车替换为换行符；
    2. 将每行首尾的多余空格去除；
    3. 将连续超过 2 个的空行压缩为 1 个空行。
    """
    # 统一行结束符
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # 清理每行行首尾空格
    lines = [line.strip() for line in text.split("\n")]
    # 压缩连续空行（超过 2 个压缩为 1 个）
    cleaned_lines: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def clean_text(raw: str) -> str:
    """
    主入口：对原始攻略文本执行完整清洗流水线。

    清洗步骤（顺序执行）：
      1. 去除 HTML 标签（strip_html）
      2. 去除 emoji 表情符号（strip_emoji）
      3. 去除广告话术（strip_ad_phrases）
      4. 规范化空白（normalize_whitespace）

    参数:
        raw: 用户导入的原始文本，可能包含 HTML、emoji、广告词等。

    返回:
        干净的纯文本字符串，适合直接送入分块器。
    """
    text = strip_html(raw)
    text = strip_emoji(text)
    text = strip_ad_phrases(text)
    text = normalize_whitespace(text)
    return text
