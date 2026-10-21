# -*- coding: utf-8 -*-
"""Собирает статический сайт из запущенного приложения: страницы + static + API-JSON."""
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import httpx

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"

PAGES = {
    "index": "/",
    "inbox": "/inbox",
    "sales_clients": "/report/sales_clients",
    "sales_products": "/report/sales_products",
    "top_products": "/report/top_products",
    "top_clients": "/report/top_clients",
    "dynamics": "/report/dynamics",
    "forecast": "/report/forecast",
    "pvh": "/report/pvh",
    "inventory": "/report/inventory",
    "stock_dynamics": "/report/stock_dynamics",
    "nelikvid": "/report/nelikvid",
    "debt": "/report/debt",
    "debt_manager": "/report/debt_manager",
    "clients": "/report/clients",
    "edo": "/report/edo",
}

SHIM = """
<script>
/* Демо-режим: API заменён статическими JSON-файлами */
(function () {
  var ORIG = window.fetch;
  window.fetch = function (input, init) {
    try {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf("/api/") === 0) {
        var clean = url.split("?")[0];
        var m;
        if ((m = clean.match(/^\\/api\\/generate\\/([a-z_]+)/))) return ORIG.call(window, "api/generate/" + m[1] + ".json");
        if ((m = clean.match(/^\\/api\\/analyze\\/([a-z_]+)/))) return ORIG.call(window, "api/analyze/" + m[1] + ".json");
        if (clean.indexOf("/api/inbox/files") === 0 || clean.indexOf("/api/inbox/folder") === 0) return ORIG.call(window, "api/inbox.json");
        if ((m = clean.match(/^\\/api\\/download\\/([^/]+)/))) return ORIG.call(window, "api/files/" + decodeURIComponent(m[1]));
        if ((m = clean.match(/^\\/api\\/note_file\\/([^/]+)/))) return ORIG.call(window, "api/notes/" + decodeURIComponent(m[1]));
        if (clean.indexOf("/api/upload") === 0) {
          return Promise.resolve(new Response(
            JSON.stringify({ ok: true, message: "Демо-режим: загрузка выгрузок недоступна" }),
            { status: 200, headers: { "Content-Type": "application/json; charset=utf-8" } }));
        }
      }
    } catch (e) {}
    return ORIG.call(window, input, init);
  };
  window.addEventListener("DOMContentLoaded", function () {
    var b = document.createElement("div");
    b.textContent = "ДЕМО · данные статичны";
    b.style.cssText = "position:fixed;bottom:10px;right:10px;z-index:99999;font-size:11px;" +
      "color:#9aa0a6;background:#101418ee;border:1px solid #2a2f36;border-radius:8px;padding:4px 9px;font-family:monospace";
    document.body.appendChild(b);
    // демо: отчёты формируются сразу при загрузке страницы
    setTimeout(function () {
      if (typeof generateReport === "function") { try { generateReport(); } catch (e) {} }
    }, 400);
    setTimeout(function () {
      if (typeof generateNote === "function") { try { generateNote(false); } catch (e) {} }
    }, 900);
  });
})();
</script>
"""

client = httpx.Client(base_url=BASE, timeout=120, follow_redirects=True)
SITE.mkdir(exist_ok=True)

for name, path in PAGES.items():
    r = client.get(path)
    if r.status_code != 200:
        print(f"PAGE {name}: HTTP {r.status_code}")
        continue
    html = r.text
    # пути к статике
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    # навигация
    html = re.sub(r'href="/report/([a-z_]+)"', r'href="\1.html"', html)
    html = re.sub(r'href="/inbox"', 'href="inbox.html"', html)
    html = re.sub(r'href="/"', 'href="index.html"', html)
    # shim сразу после <head>
    html = html.replace("<head>", "<head>" + SHIM, 1)
    (SITE / f"{name}.html").write_text(html, encoding="utf-8")
    print(f"PAGE {name}: {len(html)} bytes")

# static
dst_static = SITE / "static"
if dst_static.exists():
    shutil.rmtree(dst_static)
shutil.copytree(ROOT / "app" / "static", dst_static)
print("static: copied")

# скачиваемые xlsx
files_dir = SITE / "api" / "files"
files_dir.mkdir(parents=True, exist_ok=True)
n = 0
if (ROOT / "reports").is_dir():
    for f in (ROOT / "reports").glob("*.xlsx"):
        shutil.copy2(f, files_dir / f.name)
        n += 1
print(f"files: {n} xlsx")

# .md-записки из базы знаний
notes_dir = SITE / "api" / "notes"
notes_dir.mkdir(parents=True, exist_ok=True)
kn = ROOT / "data" / "06 - Аналитика и отчёты"
if not kn.is_dir():
    kn = ROOT / "06 - Аналитика и отчёты"
n2 = 0
if kn.is_dir():
    for f in kn.rglob("*.md"):
        shutil.copy2(f, notes_dir / f.name)
        n2 += 1
print(f"notes: {n2} md")

print("DONE ->", SITE)
