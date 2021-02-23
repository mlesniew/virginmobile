#!/usr/bin/env python3
"""
Download call history from www.virginmobile.pl.

Usage:
    virgin.py [options] <number> last <count> days
    virgin.py [options] <number> year <year>
    virgin.py [options] <number> month <year> <month>
    virgin.py [options] cat <file>...

Options:
    -c, --csv                   Produce CSV output instead of a table
    -u USER, --username USER    Set username
    -p PASS, --password PASS    Set password
    -n, --no-interactive        Don't ask questions
"""
from datetime import datetime, timedelta
from getpass import getpass
from collections import defaultdict
import csv
import dataclasses
import sys

from docopt import docopt
from tabulate import tabulate
import requests


@dataclasses.dataclass(frozen=True, order=True)
class Entry:
    date: datetime
    type: str
    direction: str
    quantity: int
    cost: float
    number: str


class VirginMobile(object):
    def __init__(self):
        self.session = requests.session()

    def login(self, username, password):
        resp = self.session.post(
            "https://virginmobile.pl/spitfire-web-api/api/v1/authentication/login",
            data={
                "username": username,
                "password": password,
            },
        )
        resp.raise_for_status()

    def iter_history_month(self, number, year, month):
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        end -= timedelta(seconds=1)
        return self.iter_history(number, start, end)

    def iter_history_year(self, number, year):
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        end -= timedelta(seconds=1)
        return self.iter_history(number, start, end)

    def iter_history_days(self, number, count):
        end = datetime.utcnow()
        start = end - timedelta(days=count)
        return self.iter_history(number, start, end)

    def iter_history(self, number, start, end):
        step = timedelta(days=15)
        end = min(end, datetime.utcnow())
        while start <= end:
            nend = min(end, start + step)
            for item in self.iter_history_step(number, start, nend):
                yield item
            start += step

    def iter_history_step(self, number, start, end):
        FMT = "%Y-%m-%dT%H:%M:%S"
        FMT2 = FMT + ".000+0000"
        page = 0
        pageSize = 500
        while True:
            params = {
                "start": start.strftime(FMT),
                "end": end.strftime(FMT),
                "page": page,
                "pageSize": pageSize,
            }
            resp = self.session.get(
                "https://virginmobile.pl/spitfire-web-api/api/v1/selfCare/callHistory",
                params=params,
                headers={"msisdn": number, "Accept": "application/json"},
            )

            resp.raise_for_status()
            result = resp.json()
            for element in result["records"]:
                yield Entry(
                    datetime.strptime(element["date"], FMT2),
                    element["type"],
                    element["direction"],
                    int(element["quantity"]),
                    float(element["price"]),
                    element["number"],
                )

            if len(result["records"]) < pageSize:
                break

            page += 1


def cat(a, b):
    c = defaultdict(list)
    for elements in [a, b]:
        for e in elements:
            key = (e.date, e.type)
            c[key].append(e)
    for key in sorted(c):
        elements = c[key]
        quantities = set(e.quantity for e in elements)
        assert key[1] == "DATA" or len(quantities) == 1
        yield max(elements, key=lambda e: e.quantity)


def main():
    args = docopt(__doc__)

    if args["cat"]:
        entries = []
        for filename in args["<file>"]:
            with open(filename, "r", encoding="utf-8") as f:
                csv_entries = (
                    Entry(
                        datetime.fromisoformat(element["date"]),
                        element["type"],
                        element["direction"],
                        int(element["quantity"]),
                        float(element["cost"]),
                        element["number"],
                    )
                    for element in csv.DictReader(f)
                )
                entries = list(cat(entries, csv_entries))
    else:
        number = args["<number>"]

        username = args["--username"]
        if username is None:
            if args["--no-interactive"]:
                raise SystemExit("No username given")
            else:
                username = input("username:")

        password = args["--password"]
        if password is None:
            if args["--no-interactive"]:
                raise SystemExit("No password given")
            else:
                password = getpass("password:")

        vm = VirginMobile()
        vm.login(username, password)

        if args["last"]:
            count = int(args["<count>"])
            entries = vm.iter_history_days(number, count)
        else:
            if args["year"]:
                year = int(args["<year>"])
                entries = vm.iter_history_year(number, year)
            elif args["month"]:
                year = int(args["<year>"])
                month = int(args["<month>"])
                entries = vm.iter_history_month(number, year, month)

    entries = sorted(set(entries))
    FIELDS = [f.name for f in dataclasses.fields(Entry)]
    if not args["--csv"]:
        print(
            tabulate(
                [dataclasses.astuple(e) for e in entries],
                headers=FIELDS,
            )
        )
    else:
        writer = csv.DictWriter(sys.stdout, FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(dataclasses.asdict(entry))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Aborted.")
