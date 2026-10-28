"""Plain-text citation templates. No code or markup is evaluated."""

import re


FIELDS = {
    "authors", "author", "year", "title", "journal", "volume", "issue",
    "pages", "publisher", "doi", "doiUrl", "number", "locator",
}
TOKEN = re.compile(r"\{([a-zA-Z]+)\}")
OPTIONAL = re.compile(r"\[\[([^\[\]]*)\]\]")


def validate_custom_style(value):
    if not isinstance(value, dict):
        raise ValueError("カスタム様式の定義がありません。")
    name = value.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("様式名を80文字以内で入力してください。")
    if value.get("kind") not in {"numeric", "author-date"}:
        raise ValueError("引用形式を選択してください。")
    if not isinstance(value.get("superscript", False), bool):
        raise ValueError("上付きの指定が不正です。")
    for key in ("citationTemplate", "bibliographyTemplate"):
        template = value.get(key)
        if not isinstance(template, str) or not template.strip() or len(template) > 2000:
            raise ValueError("本文・参考文献のテンプレートを2000文字以内で入力してください。")
        fields = TOKEN.findall(template)
        if not fields or set(fields) - FIELDS:
            raise ValueError("テンプレートに使用できない項目があります。項目一覧を確認してください。")
        remainder = TOKEN.sub("", template)
        if "{" in remainder or "}" in remainder:
            raise ValueError("項目は {title} のように指定してください。")
        remainder = OPTIONAL.sub("", template)
        if "[[" in remainder or "]]" in remainder:
            raise ValueError("省略可能な部分は [[...]] で囲んでください。入れ子は使用できません。")
        if value["kind"] == "numeric" and "number" not in fields:
            raise ValueError("番号形式では本文・参考文献の両方に {number} を含めてください。")
        if value["kind"] == "author-date" and "number" in fields:
            raise ValueError("{number} は番号形式で使用してください。")
    return {
        "name": name.strip(), "kind": value["kind"],
        "superscript": value.get("superscript", False) and value["kind"] == "numeric",
        "citationTemplate": value["citationTemplate"].strip(),
        "bibliographyTemplate": value["bibliographyTemplate"].strip(),
    }


def render_template(template, values):
    def optional(match):
        fields = TOKEN.findall(match[1])
        return match[1] if all(values.get(field, "") != "" for field in fields) else ""

    template = OPTIONAL.sub(optional, template)
    return TOKEN.sub(lambda match: str(values.get(match[1], "")), template).strip()


def format_custom(paper, definition, template_key, number=None, locator=None):
    # Imported here to keep the standard formatters independent of template validation.
    from .bunken_service import author_year_label, normalize_doi_value, year_label

    definition = validate_custom_style(definition)
    if definition["kind"] == "numeric" and (type(number) is not int or number < 1):
        raise ValueError("番号形式には1以上の引用番号が必要です。")
    doi = normalize_doi_value(paper.doi)
    values = {
        "authors": paper.authors or "Unknown", "author": author_year_label(paper.authors),
        "year": year_label(paper.year), "title": paper.title or "",
        "journal": paper.journal or "", "volume": paper.volume or "",
        "issue": paper.issue or "", "pages": paper.pages or "",
        "publisher": paper.publisher or "", "doi": doi,
        "doiUrl": f"https://doi.org/{doi}" if doi else "",
        "number": str(number) if number is not None else "", "locator": locator or "",
    }
    return render_template(definition[template_key], values)
