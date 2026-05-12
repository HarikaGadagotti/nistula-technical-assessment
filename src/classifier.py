import re
from models import QueryType

_COMPLAINT_PATTERNS = [
    r"\bnot working\b", r"\bbroken\b", r"\bunacceptable\b", r"\brefund\b",
    r"\bcomplain\b", r"\bterrible\b", r"\bno hot water\b", r"\bno water\b",
    r"\bno power\b", r"\bdirty\b", r"\bdisappoint\b", r"\bnot happy\b",
    r"\bunhappy\b", r"\bangry\b",
]

_SPECIAL_REQUEST_PATTERNS = [
    r"\bearly check.?in\b", r"\blate check.?out\b", r"\bairport.?transfer\b",
    r"\bpick.?up\b", r"\bdrop.?off\b", r"\bdecorat\b", r"\bcake\b",
    r"\banniversary\b", r"\bbirthday\b", r"\bspecial\b", r"\bflower\b",
]

_POST_SALES_CHECKIN_PATTERNS = [
    r"\bcheck.?in time\b", r"\bcheck.?out time\b", r"\bwifi\b", r"\bwi-fi\b",
    r"\bpassword\b", r"\bcaretaker\b", r"\bdirections?\b", r"\bhow to get\b",
    r"\bkey\b", r"\baccess\b", r"\bpark\b",
]

_PRE_SALES_PRICING_PATTERNS = [
    r"\brate\b", r"\bprice\b", r"\bcost\b", r"\bhow much\b", r"\bcharge\b",
    r"\bfee\b", r"\bquote\b", r"\bper night\b", r"\bper person\b", r"\bdiscount\b",
]

_PRE_SALES_AVAILABILITY_PATTERNS = [
    r"\bavailab\b", r"\bbook\b", r"\breserv\b", r"\bdates?\b",
    r"\bapril\b", r"\bmay\b", r"\bjune\b", r"\bjuly\b",
    r"\bfrom\s+\w+\s+\d+",
]


def classify_query(message: str) -> QueryType:
    text = message.lower()

    def matches(patterns):
        return any(re.search(p, text) for p in patterns)

    if matches(_COMPLAINT_PATTERNS):
        return QueryType.complaint
    if matches(_SPECIAL_REQUEST_PATTERNS):
        return QueryType.special_request
    if matches(_POST_SALES_CHECKIN_PATTERNS):
        return QueryType.post_sales_checkin

    pricing_score = sum(1 for p in _PRE_SALES_PRICING_PATTERNS if re.search(p, text))
    avail_score = sum(1 for p in _PRE_SALES_AVAILABILITY_PATTERNS if re.search(p, text))

    if pricing_score > 0 or avail_score > 0:
        return QueryType.pre_sales_availability if avail_score >= pricing_score else QueryType.pre_sales_pricing

    return QueryType.general_enquiry