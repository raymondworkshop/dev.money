"""Institutional flow heuristics from price + volume (accumulation / distribution)."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
USER_AGENT = "dev.business-flow/1.0 (personal research; +https://localhost)"

LOOKBACK_DAYS = 50
WEEK_LOOKBACK = 8  # shorter → more sensitive than 12
AVG_VOLUME_WINDOW = 50
HIGH_VOLUME_MULT = 1.3  # was 1.5; catch milder volume spikes
HIGH_CLOSE_PCT = 0.70
LOW_CLOSE_PCT = 0.30
DISTRIBUTION_DAY_DROP = 0.002  # 0.2%
DISTRIBUTION_DAY_WINDOW = 15  # was 20; "short period" tighter


@dataclass
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class WeekBar:
    week_end: date
    high: float
    low: float
    close: float
    volume: float
    close_pct: float  # 0–1 within week's range
    vs_avg_volume: float


@dataclass
class FlowReport:
    ticker: str
    as_of: date
    bars: int
    up_down_volume_ratio: float | None
    avg_daily_volume: float
    accumulation_weeks: list[WeekBar] = field(default_factory=list)
    distribution_weeks: list[WeekBar] = field(default_factory=list)
    recent_weeks: list[WeekBar] = field(default_factory=list)
    pullback_weeks_low_volume: int = 0
    pullback_weeks_high_volume: int = 0
    distribution_days: int = 0
    signal: str = "中性"
    reasons: list[str] = field(default_factory=list)
    caveat: str = (
        "这只是用价格和成交量粗粗看一眼，不是叫你买或卖。"
        "成交量大，也不一定就是大机构；也可能只是很多人在短线买卖。"
    )


def _http_get(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_daily_bars(ticker: str, range_: str = "1y") -> list[Bar]:
    """Fetch daily OHLCV from Yahoo Finance chart API (stdlib only)."""
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("ticker is empty")

    qs = urllib.parse.urlencode({"interval": "1d", "range": range_})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{qs}"
    try:
        raw = _http_get(url)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Yahoo chart HTTP {exc.code} for {symbol}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Yahoo chart network error for {symbol}: {exc.reason}") from exc

    payload = json.loads(raw.decode("utf-8"))
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        err = (payload.get("chart") or {}).get("error") or {}
        raise RuntimeError(f"No chart data for {symbol}: {err.get('description') or err}")

    node = result[0]
    timestamps = node.get("timestamp") or []
    quote = ((node.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    bars: list[Bar] = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = (
            _num(opens, i),
            _num(highs, i),
            _num(lows, i),
            _num(closes, i),
            _num(volumes, i),
        )
        if None in (o, h, l, c, v) or c <= 0 or v < 0:
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        bars.append(Bar(day=day, open=o, high=h, low=l, close=c, volume=v))

    if len(bars) < LOOKBACK_DAYS:
        raise RuntimeError(f"Need ≥{LOOKBACK_DAYS} daily bars for {symbol}, got {len(bars)}")
    return bars


def _num(series: list[Any], i: int) -> float | None:
    if i >= len(series):
        return None
    val = series[i]
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def up_down_volume_ratio(bars: list[Bar], lookback: int = LOOKBACK_DAYS) -> float | None:
    window = bars[-lookback:] if len(bars) >= lookback else bars
    if len(window) < 2:
        return None
    up_vol = 0.0
    down_vol = 0.0
    for i in range(1, len(window)):
        prev, cur = window[i - 1], window[i]
        if cur.close > prev.close:
            up_vol += cur.volume
        elif cur.close < prev.close:
            down_vol += cur.volume
    if down_vol <= 0:
        return None if up_vol <= 0 else float("inf")
    return up_vol / down_vol


def average_volume(bars: list[Bar], lookback: int = AVG_VOLUME_WINDOW) -> float:
    window = bars[-lookback:] if len(bars) >= lookback else bars
    if not window:
        return 0.0
    return sum(b.volume for b in window) / len(window)


def _iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return iso.year, iso.week


def aggregate_weeks(bars: list[Bar]) -> list[WeekBar]:
    if not bars:
        return []
    groups: dict[tuple[int, int], list[Bar]] = {}
    order: list[tuple[int, int]] = []
    for b in bars:
        key = _iso_week_key(b.day)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(b)

    raw_weeks: list[tuple[date, float, float, float, float]] = []
    for key in order:
        g = groups[key]
        high = max(x.high for x in g)
        low = min(x.low for x in g)
        close = g[-1].close
        vol = sum(x.volume for x in g)
        raw_weeks.append((g[-1].day, high, low, close, vol))

    vols = [w[4] for w in raw_weeks]
    out: list[WeekBar] = []
    for i, (week_end, high, low, close, vol) in enumerate(raw_weeks):
        span = high - low
        close_pct = 0.5 if span <= 0 else max(0.0, min(1.0, (close - low) / span))
        # trailing average of prior weeks (exclude current)
        prior = vols[max(0, i - WEEK_LOOKBACK) : i]
        avg = (sum(prior) / len(prior)) if prior else vol
        vs = (vol / avg) if avg > 0 else 1.0
        out.append(
            WeekBar(
                week_end=week_end,
                high=high,
                low=low,
                close=close,
                volume=vol,
                close_pct=close_pct,
                vs_avg_volume=vs,
            )
        )
    return out


def count_distribution_days(
    bars: list[Bar],
    avg_vol: float,
    window: int = DISTRIBUTION_DAY_WINDOW,
    drop: float = DISTRIBUTION_DAY_DROP,
    vol_mult: float = HIGH_VOLUME_MULT,
) -> int:
    if len(bars) < 2 or avg_vol <= 0:
        return 0
    segment = bars[-(window + 1) :]
    count = 0
    for i in range(1, len(segment)):
        prev, cur = segment[i - 1], segment[i]
        chg = (cur.close - prev.close) / prev.close if prev.close else 0.0
        if chg <= -drop and cur.volume >= avg_vol * vol_mult:
            count += 1
    return count


def evaluate_flow(ticker: str, bars: list[Bar]) -> FlowReport:
    symbol = ticker.strip().upper()
    ratio = up_down_volume_ratio(bars)
    avg_vol = average_volume(bars)
    weeks = aggregate_weeks(bars)
    recent = weeks[-WEEK_LOOKBACK:] if weeks else []

    accum = [
        w
        for w in recent
        if w.close_pct >= HIGH_CLOSE_PCT and w.vs_avg_volume >= HIGH_VOLUME_MULT
    ]
    distrib = [
        w
        for w in recent
        if w.close_pct <= LOW_CLOSE_PCT and w.vs_avg_volume >= HIGH_VOLUME_MULT
    ]

    # pullbacks: weeks that closed lower vs prior week
    low_vol_pb = 0
    high_vol_pb = 0
    for i in range(1, len(recent)):
        prev, cur = recent[i - 1], recent[i]
        if cur.close < prev.close:
            if cur.vs_avg_volume < 1.0:
                low_vol_pb += 1
            elif cur.vs_avg_volume >= HIGH_VOLUME_MULT:
                high_vol_pb += 1

    dist_days = count_distribution_days(bars, avg_vol)

    score = 0
    reasons: list[str] = []

    if ratio is None:
        reasons.append(
            f"近{LOOKBACK_DAYS}天里，没法比较「涨的日子」和「跌的日子」谁成交更多（数据不够）。"
        )
    elif math.isinf(ratio):
        score += 2
        reasons.append(
            f"近{LOOKBACK_DAYS}天几乎都是涨的时候成交特别多，更像有人在抢着买。"
        )
    else:
        if ratio >= 2.0:
            score += 2
            reasons.append(
                f"近{LOOKBACK_DAYS}天：涨的日子一共成交的量，大约是跌的日子的 {ratio:.1f} 倍"
                f"（数字 {ratio:.2f}，到 2 以上通常算偏强）。"
                f"涨的时候更热闹，更像买的人比较积极。"
            )
        elif ratio < 1.0:
            score -= 2
            reasons.append(
                f"近{LOOKBACK_DAYS}天：跌的日子一共成交的量，比涨的日子还多"
                f"（数字 {ratio:.2f}，小于 1）。"
                f"跌的时候更热闹，更像卖的人比较积极。"
            )
        else:
            reasons.append(
                f"近{LOOKBACK_DAYS}天：涨的日子和跌的日子，成交量差不多"
                f"（数字 {ratio:.2f}，接近 1）。两边都差不多，看不出一边倒。"
            )

    if accum:
        score += min(2, len(accum))
        last = accum[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周里，有 {len(accum)} 周更像「有人在买」："
            f"那一周结束时，价格收在靠近本周最高价的地方，而且成交量比平时明显更大。"
            f"最近一次是到 {last.week_end} 那一周："
            f"收盘很靠近本周最高价（从最低到最高大约走到 {last.close_pct:.0%}），"
            f"成交量大约是平时的 {last.vs_avg_volume:.1f} 倍。"
        )
    else:
        reasons.append(
            f"近{WEEK_LOOKBACK}周里，没有出现这种一周："
            f"收盘靠近本周最高价，同时成交量又明显变大。"
        )

    if distrib:
        score -= min(2, len(distrib))
        last = distrib[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周里，有 {len(distrib)} 周更像「有人在卖」："
            f"那一周结束时，价格收在靠近本周最低价的地方，而且成交量比平时明显更大。"
            f"最近一次是到 {last.week_end} 那一周："
            f"收盘很靠近本周最低价（从最低到最高大约只走到 {last.close_pct:.0%}），"
            f"成交量大约是平时的 {last.vs_avg_volume:.1f} 倍。"
        )
    else:
        reasons.append(
            f"近{WEEK_LOOKBACK}周里，没有出现这种一周："
            f"收盘靠近本周最低价，同时成交量又明显变大。"
        )

    if low_vol_pb and not high_vol_pb:
        score += 1
        reasons.append(
            f"中间有几周价格往下走，但成交量大多不大"
            f"（成交偏少的下跌周 {low_vol_pb} 个，成交很大的下跌周 {high_vol_pb} 个）。"
            f"更像暂时歇一歇，不像急着卖掉。"
        )
    elif high_vol_pb and high_vol_pb >= low_vol_pb:
        score -= 1
        reasons.append(
            f"中间有几周价格往下走，而且不少周成交量还很大"
            f"（成交很大的下跌周 {high_vol_pb} 个，成交偏少的下跌周 {low_vol_pb} 个）。"
            f"更像下跌时也有人在卖。"
        )

    if dist_days >= 3:
        score -= 2
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天里，有 {dist_days} 天是「跌得比较明显，成交量又很大」"
            f"（单日至少跌 {DISTRIBUTION_DAY_DROP*100:.1f}%）。"
            f"短时间出现好几次，要当心有人在往外撤。"
        )
    elif dist_days == 1:
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天里，只有 {dist_days} 天是「跌得比较明显且成交量很大」。"
            f"一天还不算什么，看看后面会不会连着出现。"
        )
    elif dist_days == 2:
        score -= 1
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天里，有 {dist_days} 天「跌得比较明显且成交量很大」，"
            f"算提个醒，还不算很严重。"
        )
    else:
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天里，没有「跌得比较明显且成交量很大」的日子。"
        )

    if score >= 2:
        signal = "看起来更像有人在买"
    elif score == 1:
        signal = "稍微偏向有人在买"
    elif score <= -2:
        signal = "看起来更像有人在卖"
    elif score == -1:
        signal = "稍微偏向有人在卖"
    else:
        signal = "暂时看不太出来"

    return FlowReport(
        ticker=symbol,
        as_of=bars[-1].day,
        bars=len(bars),
        up_down_volume_ratio=ratio,
        avg_daily_volume=avg_vol,
        accumulation_weeks=accum,
        distribution_weeks=distrib,
        recent_weeks=recent,
        pullback_weeks_low_volume=low_vol_pb,
        pullback_weeks_high_volume=high_vol_pb,
        distribution_days=dist_days,
        signal=signal,
        reasons=reasons,
    )


def _fmt_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "n/a"
    if math.isinf(ratio):
        return "∞"
    return f"{ratio:.2f}"


def judgment_rules() -> list[str]:
    return [
        "先看近一段时间：涨的日子成交多，还是跌的日子成交多。",
        "「更像在买」的一周：这一周结束时，收盘价靠近本周最高价"
        f"（至少到从最低到最高的 {int(HIGH_CLOSE_PCT * 100)}%），"
        f"而且成交量至少是平时的 {HIGH_VOLUME_MULT} 倍。",
        "「更像在卖」的一周：这一周结束时，收盘价靠近本周最低价"
        f"（只到从最低到最高的 {int(LOW_CLOSE_PCT * 100)}% 或更低），"
        f"而且成交量至少是平时的 {HIGH_VOLUME_MULT} 倍。",
        "「跌得比较明显且成交量很大」的一天：当天至少跌 "
        f"{DISTRIBUTION_DAY_DROP * 100:.1f}%，"
        f"成交量至少是平时的 {HIGH_VOLUME_MULT} 倍。",
    ]


def build_markdown(report: FlowReport) -> str:
    ratio_txt = _fmt_ratio(report.up_down_volume_ratio)
    lines = [
        f"# {report.ticker}：最近是更像有人在买，还是有人在卖？",
        "",
        f"**结论: {report.signal}**",
        "",
        "## 理由",
    ]
    lines.extend(f"- {r}" for r in report.reasons)
    lines.extend(["", "## 怎么判断的"])
    lines.extend(f"- {r}" for r in judgment_rules())
    lines.extend(
        [
            "",
            "## 数字摘要",
            f"- 数据算到: {report.as_of}",
            f"- 一共用了多少天的价格: {report.bars}",
            f"- 近{LOOKBACK_DAYS}天：涨的日子成交量 ÷ 跌的日子成交量 = {ratio_txt}"
            f"（大于 2 更像买得积极；小于 1 更像卖得积极；接近 1 差不多）",
            f"- 近{AVG_VOLUME_WINDOW}天平均每天成交多少: {report.avg_daily_volume:,.0f}",
            f"- 近{WEEK_LOOKBACK}周里「更像在买」的周数 / 「更像在卖」的周数: "
            f"{len(report.accumulation_weeks)} / {len(report.distribution_weeks)}",
            f"- 近{DISTRIBUTION_DAY_WINDOW}天里「跌得比较明显且成交量很大」的天数: "
            f"{report.distribution_days}",
        ]
    )

    if report.recent_weeks:
        lines.extend(
            [
                "",
                f"## 近{WEEK_LOOKBACK}周一览",
                "",
                "| 周结束日 | 收盘价 | 收盘有多靠近本周最高价 | 成交量是平时的几倍 | 怎么看 |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for w in report.recent_weeks:
            tag = ""
            if w in report.accumulation_weeks:
                tag = "更像在买"
            elif w in report.distribution_weeks:
                tag = "更像在卖"
            near = (
                "很靠近最高"
                if w.close_pct >= HIGH_CLOSE_PCT
                else ("很靠近最低" if w.close_pct <= LOW_CLOSE_PCT else "在中间附近")
            )
            lines.append(
                f"| {w.week_end} | {w.close:.2f} | {w.close_pct:.0%}（{near}） | "
                f"{w.vs_avg_volume:.2f} 倍 | {tag} |"
            )

    lines.extend(
        [
            "",
            f"> {report.caveat}",
            "",
            f"若想看公司赚钱情况等，可另跑: `make analyze TICKER={report.ticker}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: FlowReport, output_dir: Path | None = None) -> Path:
    target = output_dir or OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{report.ticker}_flow.md"
    path.write_text(build_markdown(report), encoding="utf-8")
    return path


def run_flow(
    ticker: str, range_: str = "1y", output_dir: Path | None = None
) -> tuple[Path, FlowReport]:
    bars = fetch_daily_bars(ticker, range_=range_)
    report = evaluate_flow(ticker, bars)
    path = write_report(report, output_dir=output_dir)
    return path, report
