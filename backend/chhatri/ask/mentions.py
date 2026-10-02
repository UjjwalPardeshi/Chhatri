"""H18: the amounts and dates in a question, found by a fixed lookup (fs-05 section 11.4).

A voice question is sent only after the merchant has confirmed one chip for each amount and each date in the final
text. `find_mentions` is that parser. It reads digits (Latin and Devanagari, with grouping commas), the number words
of `chhatri.ask.numbers`, `सौ`, `हज़ार`, `लाख`, `डेढ़`, `ढाई`, `सवा`, month names, `dd/mm`, `yesterday` and `tomorrow`.
Anything it cannot read has `value` None and its chip asks the merchant to type the number; the Hindi word `कल` means
both yesterday and tomorrow, so it is never resolved. Relative dates and missing years use the app clock (`today`).
Numbers next to a unit (days, hours, percent) and case ids such as `C-2291` are not amounts. Pure: no I/O.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from typing import Final, Literal

from chhatri.ask.copy import render_pair
from chhatri.ask.numbers import (
    ARTICLES,
    CURRENCY_AFTER,
    CURRENCY_BEFORE,
    FRACTIONS,
    HALF_PREFIX,
    MONTHS,
    MULTIPLIERS,
    NOT_MONEY_AFTER,
    SMALL_NUMBERS,
    UNSUPPORTED_NUMBERS,
    fold,
)
from chhatri.conversation.messages import date_en, date_hi
from chhatri.money import format_inr

__all__ = ["Mention", "find_mentions", "unconfirmed"]

_DEVANAGARI_DIGITS: Final = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN: Final = re.compile(r"₹|%|\d+(?:,\d+)*(?:\.\d+)?|[\wऀ-ॿ]+")
_NUMERIC_DATE: Final = re.compile(r"(?<![\d/.\-])(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?(?![\d/])")
_MAX_RUPEES: Final = 10**10
_YESTERDAY_WORDS: Final = frozenset({"yesterday"})
_TOMORROW_WORDS: Final = frozenset({"tomorrow"})
_KAL_WORDS: Final = frozenset({fold("कल"), "kal"})
_PAST_PREFIXES: Final = (("बीता", "हुआ"), ("बीते",))
_FUTURE_PREFIXES: Final = (("आने", "वाला"), ("आनेवाला",))
_AND: Final = "and"
_SMALL_TENS_UNITS_MIN: Final = 20
_TEN: Final = 10
_HUNDRED: Final = 100
_MAX_DAY_DIGITS: Final = 2


@dataclass(frozen=True, slots=True)
class Mention:
    """One amount or date the merchant must confirm."""

    id: str
    kind: Literal["amount", "date"]
    heard: str
    value: str | None
    value_paise: int | None
    value_date: date | None
    chip_hi: str
    chip_en: str

    def to_wire(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "heard": self.heard,
            "value": self.value,
            "value_paise": self.value_paise,
            "value_date": None if self.value_date is None else self.value_date.isoformat(),
            "chip_hi": self.chip_hi,
            "chip_en": self.chip_en,
        }


@dataclass(frozen=True, slots=True)
class _Tok:
    text: str
    folded: str
    start: int
    end: int

    @property
    def is_number(self) -> bool:
        return self.text[0].isdigit()


@dataclass(frozen=True, slots=True)
class _Found:
    """A mention before it gets an id: the tokens it used (`end` is the next token to scan)."""

    end: int
    kind: Literal["amount", "date"]
    heard: str
    paise: int | None = None
    day: date | None = None
    unresolved_date: bool = False


def find_mentions(text: str, *, today: date) -> tuple[Mention, ...]:
    """Every amount and date in `text`, left to right, with ids `m1`, `m2`, ... (the clock gives relative dates)."""
    folded_digits = text.translate(_DEVANAGARI_DIGITS)
    spans = [(m.start(), m.end(), m) for m in _NUMERIC_DATE.finditer(folded_digits)]
    tokens = _tokens(folded_digits, spans)
    found: list[tuple[int, _Found]] = [
        (start, _numeric_date(folded_digits[start:end], match, today)) for start, end, match in spans
    ]
    index = 0
    while index < len(tokens):
        item = _read_at(tokens, index, folded_digits, today)
        if item is None:
            index += 1
            continue
        found.append((tokens[index].start, item))
        index = item.end
    found.sort(key=lambda pair: pair[0])
    return tuple(_to_mention(f"m{number}", item) for number, (_, item) in enumerate(found, start=1))


def unconfirmed(mentions: Iterable[Mention], confirmed: Collection[str]) -> tuple[str, ...]:
    """Ids the merchant has not confirmed. A chip with no value can never be confirmed: the merchant types it."""
    return tuple(m.id for m in mentions if m.value is None or m.id not in confirmed)


# ------------------------------------------------------------------ tokens


def _tokens(text: str, numeric_dates: list[tuple[int, int, re.Match[str]]]) -> list[_Tok]:
    tokens: list[_Tok] = []
    for match in _TOKEN.finditer(text):
        if any(start <= match.start() < end for start, end, _ in numeric_dates):
            continue
        tokens.append(_Tok(match.group(), fold(match.group()), match.start(), match.end()))
    return tokens


def _is_id_part(text: str, tok: _Tok) -> bool:
    """A number glued to a letter and a hyphen is an id (C-2291, S-0142), not an amount."""
    return tok.start >= 2 and text[tok.start - 1] == "-" and text[tok.start - 2].isalpha()


def _read_at(tokens: list[_Tok], index: int, text: str, today: date) -> _Found | None:
    return (
        _month_date(tokens, index, today)
        or _relative_date(tokens, index, today)
        or _amount(tokens, index, text)
    )


# ------------------------------------------------------------------ dates


def _numeric_date(raw: str, match: re.Match[str], today: date) -> _Found:
    day, month, year_text = int(match.group(1)), int(match.group(2)), match.group(3)
    year = (
        today.year
        if year_text is None
        else (2000 + int(year_text) if len(year_text) == 2 else int(year_text))
    )
    return _Found(0, "date", raw, day=_valid_day(year, month, day))


def _valid_day(year: int, month: int, day: int) -> date | None:
    if not 1 <= month <= 12 or not 1 <= year <= 9999:
        return None
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None
    return date(year, month, day)


def _month_date(tokens: list[_Tok], index: int, today: date) -> _Found | None:
    first = tokens[index]
    nxt = tokens[index + 1] if index + 1 < len(tokens) else None
    if nxt is None:
        return None
    if first.is_number and nxt.folded in MONTHS and _is_day(first):
        return _dated(tokens, index, index + 2, int(first.text), MONTHS[nxt.folded], today)
    if first.folded in MONTHS and nxt.is_number and _is_day(nxt):
        return _dated(tokens, index, index + 2, int(nxt.text), MONTHS[first.folded], today, year_after=False)
    if first.is_number and _is_day(first) and nxt.folded in {"st", "nd", "rd", "th"}:
        month = tokens[index + 2] if index + 2 < len(tokens) else None
        if month is not None and month.folded in MONTHS:
            return _dated(tokens, index, index + 3, int(first.text), MONTHS[month.folded], today)
    return None


def _is_day(tok: _Tok) -> bool:
    return tok.text.isdigit() and len(tok.text) <= _MAX_DAY_DIGITS


def _dated(
    tokens: list[_Tok], start: int, end: int, day: int, month: int, today: date, *, year_after: bool = True
) -> _Found:
    year = today.year
    last = end
    if year_after and end < len(tokens) and tokens[end].text.isdigit() and len(tokens[end].text) == 4:  # noqa: PLR2004
        year, last = int(tokens[end].text), end + 1
    heard = _slice(tokens, start, last)
    return _Found(last, "date", heard, day=_valid_day(year, month, day))


def _relative_date(tokens: list[_Tok], index: int, today: date) -> _Found | None:
    word = tokens[index].folded
    if word in _YESTERDAY_WORDS:
        return _Found(index + 1, "date", tokens[index].text, day=today - timedelta(days=1))
    if word in _TOMORROW_WORDS:
        return _Found(index + 1, "date", tokens[index].text, day=today + timedelta(days=1))
    for prefixes, offset in ((_PAST_PREFIXES, -1), (_FUTURE_PREFIXES, 1)):
        for prefix in prefixes:
            size = len(prefix)
            window = [fold(t.text) for t in tokens[index : index + size + 1]]
            if (
                len(window) == size + 1
                and tuple(window[:size]) == tuple(fold(p) for p in prefix)
                and window[-1] in _KAL_WORDS
            ):
                return _Found(
                    index + size + 1,
                    "date",
                    _slice(tokens, index, index + size + 1),
                    day=today + timedelta(days=offset),
                )
    if word in _KAL_WORDS:
        return _Found(index + 1, "date", tokens[index].text, unresolved_date=True)
    return None


# ------------------------------------------------------------------ amounts


def _amount(tokens: list[_Tok], index: int, text: str) -> _Found | None:
    tok = tokens[index]
    if tok.is_number:
        return _digit_amount(tokens, index, text)
    return _word_amount(tokens, index)


def _digit_amount(tokens: list[_Tok], index: int, text: str) -> _Found | None:
    tok = tokens[index]
    if _is_id_part(text, tok):
        return None
    after = tokens[index + 1] if index + 1 < len(tokens) else None
    end, scale = index + 1, Fraction(1)
    if after is not None and after.folded in MULTIPLIERS:
        end, scale = index + 2, MULTIPLIERS[after.folded]
    elif after is not None and after.folded in NOT_MONEY_AFTER:
        return None
    paise = _paise(Fraction(tok.text.replace(",", "")) * scale)
    return _Found(end, "amount", _slice(tokens, index, end), paise=paise)


def _word_amount(tokens: list[_Tok], index: int) -> _Found | None:
    start_ok = _starts_number(tokens, index)
    if not start_ok:
        return None
    parsed = _parse_run(tokens, index)
    if parsed is None:
        return None
    end, value, has_multiplier, unsupported = parsed
    if not (has_multiplier or _currency_next_to(tokens, index, end)):
        return None
    after = tokens[end] if end < len(tokens) else None
    if after is not None and after.folded in NOT_MONEY_AFTER:
        return None
    paise = None if unsupported else _paise(value)
    return _Found(end, "amount", _slice(tokens, index, end), paise=paise)


def _starts_number(tokens: list[_Tok], index: int) -> bool:
    word = tokens[index].folded
    if word in SMALL_NUMBERS or word in UNSUPPORTED_NUMBERS or word in MULTIPLIERS:
        return True
    if word in FRACTIONS or word in HALF_PREFIX:
        return True
    nxt = tokens[index + 1].folded if index + 1 < len(tokens) else ""
    return word in ARTICLES and nxt in MULTIPLIERS


def _currency_next_to(tokens: list[_Tok], start: int, end: int) -> bool:
    before = tokens[start - 1].folded if start > 0 else ""
    after = tokens[end].folded if end < len(tokens) else ""
    return before in CURRENCY_BEFORE or after in CURRENCY_AFTER


def _parse_run(tokens: list[_Tok], index: int) -> tuple[int, Fraction, bool, bool] | None:
    """Read number words from `index`: `(end, value, has_multiplier, has_unsupported)`, or None when none read."""
    total, group = Fraction(0), Fraction(0)
    last_scale = None
    previous = "start"  # start, small, multiplier, other
    previous_small = Fraction(0)
    has_multiplier = unsupported = False
    position = index
    while position < len(tokens):
        word = tokens[position].folded
        step = _step(tokens, position, word, group, previous, previous_small, last_scale)
        if step is None:
            break
        kind, value, used = step
        if kind == "small":
            group += value
            previous_small = value
        elif kind == "unsupported":
            unsupported = True
        elif kind == "frac":
            group += value
        elif kind == "hundred":
            group = (group or Fraction(1)) * _HUNDRED
            has_multiplier = True
        elif kind == "big":
            total += (group or Fraction(1)) * value
            group, last_scale, has_multiplier = Fraction(0), value, True
        previous = (
            kind
            if kind in {"small", "unsupported"}
            else ("multiplier" if kind in {"hundred", "big"} else kind)
        )
        position += used
    if position == index:
        return None
    return position, total + group, has_multiplier, unsupported


def _step(
    tokens: list[_Tok],
    position: int,
    word: str,
    group: Fraction,
    previous: str,
    previous_small: Fraction,
    last_scale: Fraction | None,
) -> tuple[str, Fraction, int] | None:
    """One token of a number: `(kind, value, tokens used)`, or None when it does not continue the number."""
    if word == _AND:
        nxt = tokens[position + 1].folded if position + 1 < len(tokens) else ""
        if previous == "multiplier" and (nxt in SMALL_NUMBERS or nxt in UNSUPPORTED_NUMBERS):
            return "and", Fraction(0), 1
        return None
    if word in ARTICLES:
        nxt = tokens[position + 1].folded if position + 1 < len(tokens) else ""
        return ("small", Fraction(1), 1) if previous == "start" and nxt in MULTIPLIERS else None
    if word in SMALL_NUMBERS:
        value = SMALL_NUMBERS[word]
        return ("small", value, 1) if _may_add(previous, previous_small, value, group) else None
    if word in UNSUPPORTED_NUMBERS:
        return ("unsupported", Fraction(0), 1) if previous in {"start", "multiplier"} else None
    if word in FRACTIONS:
        return ("frac", FRACTIONS[word], 1) if previous in {"start", "multiplier"} and group == 0 else None
    if word in HALF_PREFIX:
        nxt = tokens[position + 1].folded if position + 1 < len(tokens) else ""
        if previous in {"start", "multiplier"} and nxt in SMALL_NUMBERS:
            return "frac", SMALL_NUMBERS[nxt] + Fraction(1, 2), 2
        return None
    if word in MULTIPLIERS:
        return _multiplier_step(word, group, last_scale)
    return None


def _may_add(previous: str, previous_small: Fraction, value: Fraction, group: Fraction) -> bool:
    if previous in {"start", "multiplier"}:
        return True
    if previous == "and":
        return True
    return (
        previous == "small"
        and previous_small >= _SMALL_TENS_UNITS_MIN
        and previous_small % _TEN == 0
        and 0 < value < _TEN
        and group == previous_small
    )


def _multiplier_step(
    word: str, group: Fraction, last_scale: Fraction | None
) -> tuple[str, Fraction, int] | None:
    value = MULTIPLIERS[word]
    if value == _HUNDRED:
        return ("hundred", value, 1) if group < _HUNDRED else None
    if last_scale is not None and value >= last_scale:
        return None
    return "big", value, 1


def _paise(rupees: Fraction) -> int | None:
    if rupees < 0 or rupees >= _MAX_RUPEES:
        return None
    paise = rupees * 100
    return int(paise) if paise.denominator == 1 else None


def _slice(tokens: list[_Tok], start: int, end: int) -> str:
    """The words as written, from the first token to the last one (a gap in the text is one space)."""
    pieces: list[str] = []
    for position in range(start, end):
        tok = tokens[position]
        if pieces and tok.start != tokens[position - 1].end:
            pieces.append(" ")
        pieces.append(tok.text)
    return "".join(pieces)


# ------------------------------------------------------------------ chips


def _to_mention(mention_id: str, item: _Found) -> Mention:
    if item.kind == "amount" and item.paise is not None:
        value = format_inr(item.paise)
        hi, en = render_pair("ASK_MENTION_CHIP", value=value)
        return Mention(mention_id, "amount", item.heard, value, item.paise, None, hi, en)
    if item.kind == "date" and item.day is not None:
        hi, en = (
            render_pair("ASK_MENTION_CHIP", value=date_hi(item.day))[0],
            render_pair("ASK_MENTION_CHIP", value=date_en(item.day))[1],
        )
        return Mention(mention_id, "date", item.heard, date_en(item.day), None, item.day, hi, en)
    if item.unresolved_date:
        hi, en = render_pair("KAL_ASK")
    else:
        hi, en = render_pair("ASK_MENTION_WORDS", heard=item.heard)
    return Mention(mention_id, item.kind, item.heard, None, None, None, hi, en)
