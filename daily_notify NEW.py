"""שולח התראה לטלפון (דרך ntfy) עם 'החברה היומית'. רץ אוטומטית דרך GitHub Actions."""
import datetime as dt
import json
import os
import time
import urllib.request

import yfinance as yf

try:
    yf.set_tz_cache_location("/tmp/yf-cache")
except Exception:
    pass

WINDOW = 150
SITE_URL = "https://sap150.streamlit.app"

# חשוב: אותה רשימה כמו ב-app.py, כדי שההתראה והאתר יציגו את אותה חברה.
SECTORS = {
    "טכנולוגיה": ("XLK", ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE"]),
    "בריאות": ("XLV", ["JNJ", "LLY", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT"]),
    "פיננסים": ("XLF", ["JPM", "BAC", "V", "MA", "GS", "MS", "BRK-B", "AXP"]),
    "אנרגיה": ("XLE", ["XOM", "CVX", "COP", "SLB", "EOG", "OXY"]),
    "צריכה מחזורית": ("XLY", ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "BKNG"]),
    "צריכה בסיסית": ("XLP", ["PG", "KO", "PEP", "WMT", "COST", "PM"]),
    "תעשייה": ("XLI", ["CAT", "GE", "BA", "HON", "UPS", "LMT", "DE"]),
    "תקשורת ומדיה": ("XLC", ["GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ"]),
    "חומרי גלם": ("XLB", ["LIN", "SHW", "FCX", "NEM", "DOW"]),
    "נדל\"ן": ("XLRE", ["PLD", "AMT", "EQIX", "O", "SPG"]),
    "תשתיות": ("XLU", ["NEE", "DUK", "SO", "D", "AEP"]),
}


def today_il():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    except Exception:
        return dt.date.today()


def pick_of_the_day(day):
    names = list(SECTORS)
    n = day.toordinal()
    sector = names[n % len(names)]
    etf, tickers = SECTORS[sector]
    return sector, etf, tickers[(n // len(names)) % len(tickers)]


def pct(x):
    return f"{x * 100:+.1f}%"


def load_prices(tickers, attempts=4):
    """מוריד מחירים, ובמקרה של תקלה זמנית מנסה שוב."""
    last = None
    for i in range(attempts):
        try:
            df = yf.download(tickers, period="2y", auto_adjust=True, progress=False, threads=False)["Close"].dropna()
            if len(df) >= 253 and all(t in df for t in tickers):
                return df
            last = "אין מספיק נתונים"
        except Exception as e:
            last = e
        print(f"ניסיון {i + 1} נכשל: {last}")
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"לא הצלחתי להוריד נתונים עבור {tickers}: {last}")


def build_report(today):
    sector, etf, ticker = pick_of_the_day(today)

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    name = info.get("longName", ticker)

    prices = load_prices([ticker, "^GSPC", etf])

    stock, spx, sec = prices[ticker], prices["^GSPC"], prices[etf]
    price = float(stock.iloc[-1])
    avg = float(stock.tail(WINDOW).mean())
    d1 = stock.iloc[-1] / stock.iloc[-2] - 1
    m1 = stock.iloc[-1] / stock.iloc[-22] - 1
    y1 = stock.iloc[-1] / stock.iloc[-253] - 1
    hi, lo = float(stock.tail(252).max()), float(stock.tail(252).min())
    side = "מעל" if price > avg else "מתחת ל"

    status = [
        f"מחיר אחרון: {price:,.2f} ({pct(d1)} ביום האחרון)",
        f"חודש: {pct(m1)} · שנה: {pct(y1)}",
        f"המניה {side}ממוצע {WINDOW} יום ב-{abs(price / avg - 1) * 100:.1f}%",
        f"טווח 52 שבועות: {lo:,.2f} – {hi:,.2f} (המחיר ב-{(price - lo) / (hi - lo) * 100:.0f}% מהטווח)",
    ]
    if info.get("trailingPE"):
        status.append(f"מכפיל רווח (P/E): {info['trailingPE']:.1f}")

    rets = prices.pct_change().dropna().tail(252)
    r, m, s = rets[ticker], rets["^GSPC"], rets[etf]
    beta = r.cov(m) / m.var()
    corr_m, corr_s = r.corr(m), r.corr(s)

    if beta > 1.2:
        beta_txt = f"תנודתית יותר מהשוק: כשהמדד זז 1%, היא נוטה לזוז בערך {beta:.1f}% (בטא {beta:.2f})"
    elif beta >= 0.8:
        beta_txt = f"זזה בערך כמו השוק (בטא {beta:.2f})"
    else:
        beta_txt = f"רגועה יותר מהשוק (בטא {beta:.2f})"
    strength = "חזק" if corr_m > 0.7 else "בינוני" if corr_m > 0.4 else "חלש"
    market_in = [
        beta_txt,
        f"קשר {strength} ל-S&P 500 (מתאם {corr_m:.2f}), ומתאם {corr_s:.2f} לתחום {sector}",
        f"בימים ש-S&P 500 עלה היא עלתה בממוצע {pct(r[m > 0].mean())}, "
        f"ובימים שירד היא זזה בממוצע {pct(r[m < 0].mean())}",
    ]

    mc = info.get("marketCap")
    if mc:
        b = mc / 1e9
        if b >= 500:
            note = "חברת ענק, תנועות שלה משפיעות על המדדים עצמם"
        elif b >= 100:
            note = "חברה גדולה, יש לה משקל מורגש במדד אבל לא מכריע"
        else:
            note = "קטנה יחסית, השפעתה על המדד זניחה והיא מושפעת מהשוק הרבה יותר משהיא משפיעה עליו"
        market_out = [f"שווי שוק: כ-{b:,.0f} מיליארד דולר. {note}"]
    else:
        market_out = ["אין נתון על שווי שוק"]

    spx_y = spx.iloc[-1] / spx.iloc[-253] - 1
    sec_y = sec.iloc[-1] / sec.iloc[-253] - 1
    relative = [f"מול S&P 500: {pct(y1 - spx_y)} · מול התחום ({etf}): {pct(y1 - sec_y)}"]

    sections = [
        ("מצב המניה", status),
        ("איך השוק משפיע עליה", market_in),
        ("איך היא משפיעה על השוק", market_out),
        ("ביצועים יחסיים (שנה)", relative),
    ]
    return name, ticker, sector, sections


def build_message(sections):
    lines = []
    for title, items in sections:
        lines.append(title)
        lines += [f"• {i}" for i in items]
        lines.append("")
    lines.append("כלי מידע בלבד, לא המלצה להשקעה.")
    text = "\n".join(lines)
    # ntfy מגביל הודעה ל-4096 בייטים
    return text.encode("utf-8")[:3900].decode("utf-8", errors="ignore")


def send(title, message):
    topic = os.environ["NTFY_TOPIC"].strip()
    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "click": SITE_URL,
        "tags": ["chart_with_upwards_trend"],
    }
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("ntfy status:", resp.status)


if __name__ == "__main__":
    today = today_il()
    name, ticker, sector, sections = build_report(today)
    send(f"החברה היומית: {name} ({ticker}) · {sector}", build_message(sections))
    print("Sent:", ticker)
