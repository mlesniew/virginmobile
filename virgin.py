#!/usr/bin/env python2
'''
Download call history from www.virginmobile.pl.

Usage:
    virgin.py [options] <number> year <year>
    virgin.py [options] <number> month <year> <month>

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

    def iter_history(self, number, start, end):
        step = timedelta(days=15)
        end = min(end, datetime.now())
        while start <= end:
            nend = min(end, start + step)
            for item in self.iter_history_step(number, start, nend):
                yield item
            start += step

    def iter_history_step(self, number, start, end):
        FMT = '%Y-%m-%dT%H:%M:%S'
        FMT2 = FMT + '.000+0000'
        page = 0
        pageSize = 500
        while True:
            params = {
                    'start': start.strftime(FMT),
                    'end': end.strftime(FMT),
                    'page': page,
                    'pageSize': pageSize,
                    }
            resp = self.session.get('https://virginmobile.pl/spitfire-web-api/api/v1/selfCare/callHistory',
                                    params=params,
                                    headers={
                                        'msisdn': number,
                                        'Accept': 'application/json'
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

            if len(result['records']) < pageSize:
                break

            page += 1


def main():
    args = docopt(__doc__)

    number = args['<number>']
    year = int(args['<year>'])
    month = int(args['<month>'] or 0)

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

    if args['year']:
        ret = sorted(vm.iter_history_year(number, year))
    else:
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
