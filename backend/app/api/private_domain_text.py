from app.api.private_domain_common import *  # noqa: F401,F403
from app.api.private_domain_common import router, public_router  # noqa: F401
from app.api.private_domain_schemas import *  # noqa: F401,F403
from app.api.private_domain_fallback import DEFAULT_CATEGORY_DATA  # noqa: F401

# ---------------------------------------------------------------------------
# Anti-Fold Calculation Helper
# ---------------------------------------------------------------------------

def calculate_moments_lines(text: str) -> Tuple[int, bool, str]:
    """
    Calculates estimated display lines in WeChat Moments feed.
    Standard mobile width displays approximately 22 Chinese characters per line.
    More than 6 display lines trigger the native WeChat 'Full Text' (全文) fold.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    total_lines = 0
    preview_parts: List[str] = []

    for p in paragraphs:
        p_len = len(p)
        lines_for_p = max(1, math.ceil(p_len / 22))
        if total_lines < 6:
            remaining = 6 - total_lines
            if lines_for_p <= remaining:
                preview_parts.append(p)
            else:
                visible_chars = remaining * 22
                preview_parts.append(p[:visible_chars] + "...")
        total_lines += lines_for_p

    will_fold = total_lines > 6
    fold_preview = "\n".join(preview_parts[:6])
    return total_lines, will_fold, fold_preview


def clean_mechanical_dates(text: str, natural_time: str) -> str:
    """Strips mechanical date stamps (e.g. '2024年3月15日') and replaces with natural time."""
    pattern = r"\d{4}年\d{1,2}月(?:\d{1,2}日)?|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{4}[-/.]\d{1,2}"
    matches = list(re.finditer(pattern, text))
    if not matches:
        return text
    if not natural_time:
        return re.sub(pattern, "", text)
    result = text[:matches[0].start()] + natural_time
    last_end = matches[0].end()
    for m in matches[1:]:
        result += text[last_end:m.start()] + "后来"
        last_end = m.end()
    result += text[last_end:]
    return result


def enforce_anti_fold_formatting(
    text: str,
    salutation: str,
    category: str,
    natural_time: str = "",
    length_tier: str = "standard",
) -> str:
    """
    Enforces WeChat Moments mobile feed layout constraints:
    1. Excludes mechanical date stamps (converts to natural time or strips).
    2. Opens with reader_salutation in Line 1.
    3. If length_tier is 'short': keeps ≤ 5 lines, does NOT force cliffhanger or padding lines (unfolded).
    4. If length_tier is 'standard' or 'deep': Guarantees Line 5 contains a curiosity cliffhanger hook (ends with 👇) and >= 6 lines.
    """
    text = clean_mechanical_dates(text, natural_time)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]

    default_data = DEFAULT_CATEGORY_DATA.get(category, DEFAULT_CATEGORY_DATA["专业沉淀"])
    default_hook = default_data["hook"]

    if not paragraphs:
        paragraphs = [f"{salutation}，今天聊聊这个话题。"]
    elif salutation not in paragraphs[0]:
        paragraphs[0] = f"{salutation}，{paragraphs[0]}"

    if length_tier == "short":
        short_paras = []
        cur_lines = 0
        for p in paragraphs:
            p_lines = max(1, math.ceil(len(p) / 22))
            if cur_lines + p_lines <= 5:
                short_paras.append(p)
                cur_lines += p_lines
            elif cur_lines < 5:
                rem_lines = 5 - cur_lines
                max_chars = rem_lines * 22
                truncated = p[:max_chars].rstrip()
                if truncated:
                    short_paras.append(truncated)
                    cur_lines += rem_lines
                break
            else:
                break
        if not short_paras:
            short_paras = paragraphs[:3]
        return "\n".join(short_paras)

    if len(paragraphs) < 5:
        while len(paragraphs) < 4:
            paragraphs.append("调养从来不是一场冲刺，而是一场水滴石穿的生活修养。")
        paragraphs.append(default_hook)
        paragraphs.append("把步子放慢一点，让气血和心神真正归位。")
    else:
        line_5 = paragraphs[4]
        if "👇" not in line_5 and "👉" not in line_5:
            if any(k in line_5 for k in ["关键", "秘密", "其实", "核心", "不知道", "答案", "第三点"]):
                paragraphs[4] = f"{line_5}👇"
            else:
                paragraphs[4] = f"{line_5}，其实关键只在这一点👇"

    if len(paragraphs) < 6:
        paragraphs.append("把步子放慢一点，让气血和心神真正归位。")

    return "\n".join(paragraphs)

