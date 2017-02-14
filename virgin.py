#!/usr/bin/env python2
'''
Download call history from www.virginmobile.pl.

Usage:
    virgin.py [options] [--table] [--username <username>] [--password <password>] <number> <year> <month>

Options:
    -t, --table                 Print results in a nice table
    -u USER, --username USER    Set username
    -p PASS, --password PASS    Set password
    -n, --no-interactive        Don't ask questions
'''
from collections import namedtuple
from datetime import datetime, timedelta
from getpass import getpass

from docopt import docopt
from tabulate import tabulate
import requests


Entry = namedtuple('Entry', 'date type direction quantity price number')


def get_end_of_month(start):
    dt = timedelta(days=1)
    ret = start
    while start.month == ret.month:
        ret += dt
    ret = ret.replace(hour=0, minute=0, second=0)
    ret -= timedelta(seconds=1)
    return ret


def get_month_range(year, month):
    start = datetime(year, month, 1)
    end = get_end_of_month(start)
    return start, end


class VirginMobile(object):

    def __init__(self):
        self.session = requests.session()

    def login(self, username, password):
        resp = self.session.post(
            'https://virginmobile.pl/spitfire-web-api/api/v1/authentication/login',
            data={
                'username': username,
                'password': password,
            })
        resp.raise_for_status()

    def iter_history_month(self, number, year, month):
        start, end = get_month_range(year, month)
        return self.iter_history(number, start, end)

    def iter_history(self, number, start, end):
        step = timedelta(days=30)
        while start <= end:
            nend = min(end, start + step)
            for item in self.iter_history_step(number, start, nend):
                yield item
            start += step

    def iter_history_step(self, number, start, end):
        FMT = '%Y-%m-%dT%H:%M:%S'
        FMT2 = FMT + '.000+0000'
        page = 0
        while True:
            resp = self.session.get('https://virginmobile.pl/spitfire-web-api/api/v1/selfCare/callHistory',
                                    params={
                                        'callType': None,
                                        'start': start.strftime(FMT),
                                        'end': end.strftime(FMT),
                                        'page': page,
                                        'pageSize': 250,
                                    },
                                    headers={
                                        'msisdn': number
                                    })

            resp.raise_for_status()
            result = resp.json()
            for element in result['records']:
                yield Entry(datetime.strptime(element['date'], FMT2),
                            element['type'],
                            element['direction'],
                            int(element['quantity']),
                            float(element['price']),
                            element['number'])

            if len(result['records']) < 250:
                break

            page += 1



def main():
    args = docopt(__doc__)

    number = args['<number>']
    year = int(args['<year>'])
    month = int(args['<month>'])

    username = args['--username']
    if username is None:
        if args['--no-interactive']:
            raise SystemExit('No username given')
        else:
            username = raw_input('username:')

    password = args['--password']
    if password is None:
        if args['--no-interactive']:
            raise SystemExit('No password given')
        else:
            password = getpass('password:')

    vm = VirginMobile()
    vm.login(username, password)
    ret = sorted(vm.iter_history_month(number, year, month))

    if args['--table']:
        print tabulate(ret, headers=Entry._fields)
    else:
        for element in ret:
            print '\t'.join(str(e) for e in element)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit('Aborted.')
