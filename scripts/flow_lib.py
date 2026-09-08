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
WEEK_LOOKBACK = 4  # primary window for scoring
CONTEXT_WEEKS = 8  # wider window shown in summary (institution campaigns often longer)
RANGE_WEEKS = 10  # support / resistance zone
VOL_AVG_WEEKS = 8
AVG_VOLUME_WINDOW = 50
HIGH_VOLUME_MULT = 1.3
HIGH_CLOSE_PCT = 0.70
LOW_CLOSE_PCT = 0.30
ZONE_PCT = 0.25
MIN_REPEAT_WEEKS = 2  # minimum repeats before week footprints add score
STRONG_TOTAL_WEEKS = 3  # ≥3 total OR ≥2 consecutive → strong label
DISTRIBUTION_DAY_DROP = 0.002  # 0.2%
DISTRIBUTION_DAY_WINDOW = 15


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
    accum_consecutive: int = 0
    distrib_consecutive: int = 0
    accum_context_count: int = 0
    distrib_context_count: int = 0
    accum_context_consecutive: int = 0
    distrib_context_consecutive: int = 0
    buy_strong: bool = False
    sell_strong: bool = False
    range_low: float | None = None
    range_high: float | None = None
    accum_at_support: list[WeekBar] = field(default_factory=list)
    distrib_at_resistance: list[WeekBar] = field(default_factory=list)
    signal: str = "暂时看不太出来"
    reasons: list[str] = field(default_factory=list)
    caveat: str = (
        "这只是用价格和成交量粗粗看一眼，不是叫你买或卖。"
        "成交量大，也不一定就是大机构；也可能只是很多人在短线买卖。"
        "机构一整段买进或卖出，常常要数周到数月；这里看的是最近有没有开始/正在留下脚印，不是已经做完。"
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
        prior = vols[max(0, i - VOL_AVG_WEEKS) : i]
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


def max_consecutive(flags: list[bool]) -> int:
    best = cur = 0
    for flag in flags:
        if flag:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def is_buy_week(w: WeekBar) -> bool:
    return w.close_pct >= HIGH_CLOSE_PCT and w.vs_avg_volume >= HIGH_VOLUME_MULT


def is_sell_week(w: WeekBar) -> bool:
    return w.close_pct <= LOW_CLOSE_PCT and w.vs_avg_volume >= HIGH_VOLUME_MULT


def trading_range(weeks: list[WeekBar]) -> tuple[float | None, float | None]:
    if not weeks:
        return None, None
    return min(w.low for w in weeks), max(w.high for w in weeks)


def near_support(w: WeekBar, range_low: float, range_high: float) -> bool:
    span = range_high - range_low
    if span <= 0:
        return False
    ceiling = range_low + ZONE_PCT * span
    return w.low <= ceiling


def near_resistance(w: WeekBar, range_low: float, range_high: float) -> bool:
    span = range_high - range_low
    if span <= 0:
        return False
    floor = range_high - ZONE_PCT * span
    return w.high >= floor


def footprint_stats(weeks: list[WeekBar]) -> tuple[list[WeekBar], list[WeekBar], int, int]:
    buy_flags = [is_buy_week(w) for w in weeks]
    sell_flags = [is_sell_week(w) for w in weeks]
    accum = [w for w, flag in zip(weeks, buy_flags) if flag]
    distrib = [w for w, flag in zip(weeks, sell_flags) if flag]
    return accum, distrib, max_consecutive(buy_flags), max_consecutive(sell_flags)


def is_strong_repeat(count: int, consecutive: int) -> bool:
    """Strong weekly evidence: ≥2 weeks AND (consecutive ≥2 OR total ≥3)."""
    if count < MIN_REPEAT_WEEKS:
        return False
    return consecutive >= MIN_REPEAT_WEEKS or count >= STRONG_TOTAL_WEEKS


def evaluate_flow(ticker: str, bars: list[Bar]) -> FlowReport:
    symbol = ticker.strip().upper()
    ratio = up_down_volume_ratio(bars)
    avg_vol = average_volume(bars)
    weeks = aggregate_weeks(bars)
    recent = weeks[-WEEK_LOOKBACK:] if weeks else []
    context = weeks[-CONTEXT_WEEKS:] if weeks else []
    range_weeks = weeks[-RANGE_WEEKS:] if weeks else []
    range_low, range_high = trading_range(range_weeks)

    accum, distrib, accum_consec, distrib_consec = footprint_stats(recent)
    accum_ctx, distrib_ctx, accum_ctx_consec, distrib_ctx_consec = footprint_stats(context)

    buy_repeat = len(accum) >= MIN_REPEAT_WEEKS or accum_consec >= MIN_REPEAT_WEEKS
    sell_repeat = len(distrib) >= MIN_REPEAT_WEEKS or distrib_consec >= MIN_REPEAT_WEEKS
    buy_strong = is_strong_repeat(len(accum), accum_consec)
    sell_strong = is_strong_repeat(len(distrib), distrib_consec)

    accum_at_support: list[WeekBar] = []
    distrib_at_resistance: list[WeekBar] = []
    if range_low is not None and range_high is not None:
        accum_at_support = [w for w in accum if near_support(w, range_low, range_high)]
        distrib_at_resistance = [
            w for w in distrib if near_resistance(w, range_low, range_high)
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
    reasons.append(
        f"说明：机构一整段买进/卖出常要大约数周到数月；"
        f"下面主看近{WEEK_LOOKBACK}周有没有脚印，并用近{CONTEXT_WEEKS}周做对照。"
    )

    # Daily ratio is auxiliary (±1), not enough alone for a strong call
    if ratio is None:
        reasons.append(
            f"近{LOOKBACK_DAYS}天里，没法比较「涨的日子」和「跌的日子」谁成交更多（数据不够）。"
        )
    elif math.isinf(ratio):
        score += 1
        reasons.append(
            f"近{LOOKBACK_DAYS}天几乎都是涨的时候成交特别多（辅助线索，偏买）。"
        )
    else:
        if ratio >= 2.0:
            score += 1
            reasons.append(
                f"近{LOOKBACK_DAYS}天：涨的日子成交量大约是跌的日子的 {ratio:.1f} 倍"
                f"（数字 {ratio:.2f}≥2，辅助偏买）。单靠这个还不够下强结论。"
            )
        elif ratio < 1.0:
            score -= 1
            reasons.append(
                f"近{LOOKBACK_DAYS}天：跌的日子成交量更大"
                f"（数字 {ratio:.2f}<1，辅助偏卖）。单靠这个还不够下强结论。"
            )
        else:
            reasons.append(
                f"近{LOOKBACK_DAYS}天：涨跌两日成交量差不多（数字 {ratio:.2f}，接近 1）。"
            )

    if buy_strong:
        score += 2
        last = accum[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周买盘脚印较成串（强）：共 {len(accum)} 周，"
            f"最多连续 {accum_consec} 周。"
            f"最近一次到 {last.week_end}：走到约 {last.close_pct:.0%}，"
            f"量约平时的 {last.vs_avg_volume:.1f} 倍。"
        )
    elif buy_repeat:
        score += 1
        last = accum[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周买盘脚印有重复（共 {len(accum)} 周，连续 {accum_consec} 周），"
            f"但还没到更强标准（要连续≥{MIN_REPEAT_WEEKS} 或总数≥{STRONG_TOTAL_WEEKS}）。"
            f"最近一次到 {last.week_end}。先记作偏弱加分。"
        )
    elif accum:
        last = accum[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周只有 {len(accum)} 周更像「有人在买」"
            f"（到 {last.week_end}）。单周不加分。"
        )
    else:
        reasons.append(
            f"近{WEEK_LOOKBACK}周没有「收高 + 成交量明显变大」的买盘周。"
        )

    if sell_strong:
        score -= 2
        last = distrib[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周卖盘脚印较成串（强）：共 {len(distrib)} 周，"
            f"最多连续 {distrib_consec} 周。"
            f"最近一次到 {last.week_end}：走到约 {last.close_pct:.0%}，"
            f"量约平时的 {last.vs_avg_volume:.1f} 倍。"
        )
    elif sell_repeat:
        score -= 1
        last = distrib[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周卖盘脚印有重复（共 {len(distrib)} 周，连续 {distrib_consec} 周），"
            f"但还没到更强标准（要连续≥{MIN_REPEAT_WEEKS} 或总数≥{STRONG_TOTAL_WEEKS}）。"
            f"最近一次到 {last.week_end}。先记作偏弱减分。"
        )
    elif distrib:
        last = distrib[-1]
        reasons.append(
            f"近{WEEK_LOOKBACK}周只有 {len(distrib)} 周更像「有人在卖」"
            f"（到 {last.week_end}）。单周不加分。"
        )
    else:
        reasons.append(
            f"近{WEEK_LOOKBACK}周没有「收低 + 成交量明显变大」的卖盘周。"
        )

    reasons.append(
        f"对照近{CONTEXT_WEEKS}周：更像在买 {len(accum_ctx)} 周（连续 {accum_ctx_consec}），"
        f"更像在卖 {len(distrib_ctx)} 周（连续 {distrib_ctx_consec}）。"
        f"若近{WEEK_LOOKBACK}周还不明显、但近{CONTEXT_WEEKS}周更成串，说明可能是更长一段操作。"
    )

    if range_low is not None and range_high is not None:
        reasons.append(
            f"近{RANGE_WEEKS}周价格大致落在 {range_low:.2f}～{range_high:.2f}。"
            f"下方约 1/4 为托价地带（支撑）；上方约 1/4 为过不去地带（阻力）。"
        )
        if accum_at_support and buy_strong:
            score += 1
            reasons.append(
                f"成串买盘周里，有 {len(accum_at_support)} 周落在下方托价地带附近，更像在支撑慢慢买。"
            )
        elif accum_at_support and buy_repeat:
            reasons.append(
                f"重复买盘周里已有落在托价地带的，但周线还不够「强成串」，支撑只作参考、暂不加分。"
            )
        elif accum_at_support:
            reasons.append("仅有的买盘周有落在托价地带附近，痕迹还弱，不加分。")
        else:
            reasons.append("近几周没有「托价地带 + 放量收高」的支撑型买盘。")

        if distrib_at_resistance and sell_strong:
            score -= 1
            reasons.append(
                f"成串卖盘周里，有 {len(distrib_at_resistance)} 周落在上方过不去地带附近，更像在阻力慢慢卖。"
            )
        elif distrib_at_resistance and sell_repeat:
            reasons.append(
                f"重复卖盘周里已有落在阻力地带的，但周线还不够「强成串」，阻力只作参考、暂不加分。"
            )
        elif distrib_at_resistance:
            reasons.append("仅有的卖盘周有落在阻力地带附近，痕迹还弱，不加分。")
        else:
            reasons.append("近几周没有「阻力地带 + 放量收低」的阻力型卖盘。")

    if low_vol_pb and not high_vol_pb:
        score += 1
        reasons.append(
            f"中间有几周价格往下走，但成交量大多不大"
            f"（轻量下跌 {low_vol_pb}、放量下跌 {high_vol_pb}）。更像歇一歇，不像急着卖。"
        )
    elif high_vol_pb and high_vol_pb >= low_vol_pb:
        score -= 1
        reasons.append(
            f"中间下跌周里放量更多"
            f"（放量下跌 {high_vol_pb}、轻量下跌 {low_vol_pb}）。更像跌的时候也有人在卖。"
        )

    if dist_days >= 3:
        score -= 1
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天有 {dist_days} 天「跌得比较明显且成交量很大」"
            f"（辅助日线线索，短时间多次）。"
        )
    elif dist_days == 1:
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天只有 {dist_days} 天「大跌且量大」；一天还不算什么。"
        )
    elif dist_days == 2:
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天有 {dist_days} 天「大跌且量大」，提个醒，仍作辅助。"
        )
    else:
        reasons.append(
            f"近{DISTRIBUTION_DAY_WINDOW}天没有「大跌且量大」的日子。"
        )

    if score >= 2 and buy_strong:
        signal = "看起来更像有人在买"
    elif score <= -2 and sell_strong:
        signal = "看起来更像有人在卖"
    elif score >= 2 and buy_repeat:
        signal = "稍微偏向有人在买（周线有重复，但还不够强成串）"
    elif score <= -2 and sell_repeat:
        signal = "稍微偏向有人在卖（周线有重复，但还不够强成串）"
    elif score >= 2:
        signal = "稍微偏向有人在买（还缺连续几周买盘脚印）"
    elif score <= -2:
        signal = "稍微偏向有人在卖（还缺连续几周卖盘脚印）"
    elif score == 1:
        signal = "稍微偏向有人在买"
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
        accum_consecutive=accum_consec,
        distrib_consecutive=distrib_consec,
        accum_context_count=len(accum_ctx),
        distrib_context_count=len(distrib_ctx),
        accum_context_consecutive=accum_ctx_consec,
        distrib_context_consecutive=distrib_ctx_consec,
        buy_strong=buy_strong,
        sell_strong=sell_strong,
        range_low=range_low,
        range_high=range_high,
        accum_at_support=accum_at_support,
        distrib_at_resistance=distrib_at_resistance,
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
        f"主看近 {WEEK_LOOKBACK} 周脚印；近 {CONTEXT_WEEKS} 周只作对照（机构整段操作常更长）。",
        f"至少 {MIN_REPEAT_WEEKS} 周同类脚印才开始给周线分；"
        f"更强结论要：已有重复，且（连续≥{MIN_REPEAT_WEEKS} 或总数≥{STRONG_TOTAL_WEEKS}）。",
        "「更像在买」的一周：收盘靠近本周最高价"
        f"（≥{int(HIGH_CLOSE_PCT * 100)}%），成交量至少平时的 {HIGH_VOLUME_MULT} 倍。",
        "「更像在卖」的一周：收盘靠近本周最低价"
        f"（≤{int(LOW_CLOSE_PCT * 100)}%），成交量至少平时的 {HIGH_VOLUME_MULT} 倍。",
        f"近 {RANGE_WEEKS} 周高低区间：下方约 {int(ZONE_PCT * 100)}% 为支撑（托价），"
        f"上方约 {int(ZONE_PCT * 100)}% 为阻力（过不去）；"
        "只有周线已「强成串」时，支撑/阻力才加分。",
        f"近 {LOOKBACK_DAYS} 日涨跌成交量比、近 {DISTRIBUTION_DAY_WINDOW} 日「大跌且量大」只是辅助，"
        "单靠日线不下强结论。",
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
            f"- 近{WEEK_LOOKBACK}周「更像在买」/「更像在卖」: "
            f"{len(report.accumulation_weeks)} / {len(report.distribution_weeks)}"
            f"（连续买 {report.accum_consecutive} / 连续卖 {report.distrib_consecutive}；"
            f"强成串：买 {('是' if report.buy_strong else '否')} / 卖 {('是' if report.sell_strong else '否')}）",
            f"- 对照近{CONTEXT_WEEKS}周「更像在买」/「更像在卖」: "
            f"{report.accum_context_count} / {report.distrib_context_count}"
            f"（连续买 {report.accum_context_consecutive} / 连续卖 {report.distrib_context_consecutive}）",
            (
                f"- 近{RANGE_WEEKS}周价格区间: {report.range_low:.2f}～{report.range_high:.2f}"
                if report.range_low is not None and report.range_high is not None
                else "- 近几周价格区间: 暂无"
            ),
            f"- 买盘落在支撑附近 / 卖盘落在阻力附近: "
            f"{len(report.accum_at_support)} / {len(report.distrib_at_resistance)}",
            f"- 近{DISTRIBUTION_DAY_WINDOW}天「大跌且量大」（辅助）: "
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
            tags: list[str] = []
            if w in report.accumulation_weeks:
                tags.append("更像在买")
            if w in report.distribution_weeks:
                tags.append("更像在卖")
            if w in report.accum_at_support:
                tags.append("靠近支撑")
            if w in report.distrib_at_resistance:
                tags.append("靠近阻力")
            tag = "；".join(tags)
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
