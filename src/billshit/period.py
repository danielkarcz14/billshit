"""Monthly numbering, issue dates and payment deadlines."""

import calendar
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Period:
    year: int
    month: int

    def __post_init__(self):
        date(self.year, self.month, 1)
        if self.year == 9999 and self.month == 12:
            raise ValueError("December 9999 has no supported due date")

    @classmethod
    def parse(cls, value: str):
        if not re.fullmatch(r"\d{2}-\d{4}", value):
            raise ValueError("expected MM-YYYY")
        month, year = map(int, value.split("-"))
        return cls(year, month)

    @classmethod
    def current(cls):
        today = date.today()
        return cls(today.year, today.month)

    @property
    def label(self) -> str:
        return f"{self.month:02d}-{self.year:04d}"

    @property
    def number(self) -> str:
        return f"{self.year:04d}{self.month:02d}01"

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def next_start(self) -> date:
        return date(self.year + (self.month == 12), self.month % 12 + 1, 1)

    @property
    def issued(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def due(self) -> date:
        following = self.next_start
        return date(following.year, following.month,
                    calendar.monthrange(following.year, following.month)[1])
