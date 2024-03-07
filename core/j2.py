import json
import os
import re
from datetime import date, datetime
from urllib.parse import quote_plus
from minify_html import minify

import bs4
from jinja2 import Environment, FileSystemLoader

re_br = re.compile(r"<br/>(\s*</)")


def jinja_quote_plus(s: str):
    return quote_plus(s)


def to_attr(s: str):
    return s.replace('"', "'")


def to_value(s: str):
    return re.sub(r'[\s&\-\'"\+]+', '-', s).lower()


def myconverter(o):
    if isinstance(o, (datetime, date)):
        return o.__str__()


def millar(value):
    if value is None:
        return "----"
    if not isinstance(value, (int, float)):
        return value
    value = "{:,.0f}".format(value).replace(",", ".")
    return value


def decimal(value):
    if not isinstance(value, (int, float)):
        return value
    if int(value) == value:
        return int(value)
    return str(value).replace(".", ",")


def mb(value):
    if not isinstance(value, (int, float)):
        return value
    v = round(value)
    if v == 0:
        v = round(value*10)/10
    if v != 0:
        return str(v)+" MB"
    value = value * 1024
    v = round(v)
    if v != 0:
        return str(v)+" KB"
    value = value * 1024
    v = round(v)
    return str(v)+" B"


def toTag(html, *args):
    if len(args) > 0:
        html = html.format(*args)
    tag = bs4.BeautifulSoup(html, 'html.parser')
    return tag


def get_default_target_links(soup: bs4.Tag):
    def _isRemote(href: str):
        proto = href.split("://")[0].lower()
        return proto in ("http", "https")

    for a in soup.select("body a"):
        href = a.attrs.get("href")
        target = a.attrs.get("target")
        if href is None:
            continue
        if target not in ("_blank", "_self", None):
            continue
        isRemote = _isRemote(href)
        if target is not None:
            if target != "_blank" and isRemote:
                continue
            if target != "_self" and not isRemote:
                continue
        yield (isRemote, a)


class Jnj2():

    def __init__(self, origen, destino, pre=None, post=None):
        self.j2_env = Environment(
            loader=FileSystemLoader(origen), trim_blocks=True)
        self.j2_env.filters['millar'] = millar
        self.j2_env.filters['decimal'] = decimal
        self.j2_env.filters['mb'] = mb
        self.j2_env.filters['quote_plus'] = jinja_quote_plus
        self.j2_env.filters['to_attr'] = to_attr
        self.j2_env.filters['to_value'] = to_value
        self.destino = destino
        self.pre = pre
        self.post = post
        self.lastArgs = None
        self.minify = os.environ.get("MINIFY") == "1"

    def save(self, template, destino=None, parse=None, **kwargs):
        self.lastArgs = kwargs
        if destino is None:
            destino = template
        out = self.j2_env.get_template(template)
        html = out.render(**kwargs)
        if self.pre:
            html = self.pre(html, **kwargs)
        if parse:
            html = parse(html, **kwargs)
        if self.post:
            html = self.post(html, **kwargs)

        html = self.do_minimity(html)
        html = self.set_target(html)

        destino = self.destino + destino
        directorio = os.path.dirname(destino)

        if not os.path.exists(directorio):
            os.makedirs(directorio)

        with open(destino, "wb") as fh:
            fh.write(bytes(html, 'UTF-8'))
        return html

    def do_minimity(self, html: str):
        if not self.minify:
            return html
        html = minify(
            html,
            do_not_minify_doctype=True,
            ensure_spec_compliant_unquoted_attribute_values=True,
            keep_spaces_between_attributes=True,
            keep_html_and_head_opening_tags=True,
            keep_closing_tags=True,
            minify_js=True,
            minify_css=True,
            remove_processing_instructions=True
        )
        blocks = ("html", "head", "body", "style", "script", "meta", "p", "div", "main", "header", "footer", "table", "tr", "tbody", "thead", "tfoot" "ol", "li", "ul", "h1", "h2", "h3", "h4", "h5", "h6")
        html = re.sub(r"<(" + "|".join(blocks) + "\b)([^>]*)>", r"\n<\1\2>\n", html)
        html = re.sub(r"</(" + "|".join(blocks) + ")>", r"\n</\1>\n", html)
        html = re.sub(r"\n\n+", r"\n", html).strip()
        return html

    def set_target(self, html):
        soup = bs4.BeautifulSoup(html, 'html.parser')
        links = tuple(get_default_target_links(soup))
        re_count = 0
        lc_count = 0
        for isRemote, a in links:
            if isRemote:
                re_count = re_count + 1
            else:
                lc_count = lc_count + 1
        def_blank = re_count > lc_count
        if def_blank:
            soup.select_one("html > head").append(
                toTag('<base target="_blank"/>')
            )
        for isRemote, a in links:
            if isRemote and not def_blank:
                a.attrs["target"] = "_blank"
            elif not isRemote and def_blank:
                a.attrs["target"] = "_self"
            elif "target" in a.attrs:
                del a.attrs["target"]
        return str(soup)

    def create_script(self, destino, replace=False, **kargv):
        destino = self.destino + destino
        if not replace and os.path.isfile(destino):
            return
        indent = 2
        if self.minify:
            indent = None
        separators = (',', ':') if indent is None else None
        with open(destino, "w") as f:
            for i, (k, v) in enumerate(kargv.items()):
                if i > 0:
                    f.write("\n")
                f.write("const "+k+" = ")
                if not isinstance(v, str):
                    json.dump(
                        v,
                        f,
                        indent=indent,
                        separators=separators,
                        default=myconverter
                    )
                else:
                    f.write(v)
                f.write(";")

    def exists(self, destino):
        destino = self.destino + destino
        return os.path.isfile(destino)
