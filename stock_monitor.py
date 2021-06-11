import pickle
import urllib.request
import json
import os
from time import time, sleep, strftime, gmtime
import datetime

import argparse
from gooey import Gooey
from gooey import GooeyParser
from tqdm import tqdm

from screen_shooter import ScreenShooter


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_file_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_file, 'r').readlines()]
        self.output_dir = args.output_dir
        self.screenshoter = ScreenShooter(wait_time=0)
        os.makedirs(os.path.join(args.output_dir, "change_logs"), exist_ok=True)
        os.makedirs(os.path.join(args.output_dir, "status_images"), exist_ok=True)
        self.cache_path = os.path.join(args.output_dir, "monitor_cache.pkl")

        print(f"Taking base screen shots. this will take at least up to {self.screenshoter.wait_time*len(self.stock_names)} seconds")
        for stock_name in tqdm(self.stock_names):
            self.screenhost_stock(stock_name)
        print(f"ignore fields: {self.ignore_fields}")

        self.screenshoter.wait_time = 3

    def screenhost_stock(self, stock_name):
        dirname = os.path.join(self.output_dir, "status_images", stock_name)
        os.makedirs(dirname, exist_ok=True)
        for tab_name in ['profile', 'overview']:
            last_path = os.path.join(dirname, f"{tab_name}-last.png")
            if os.path.exists(last_path):
                before_last_path = os.path.join(dirname, f"{tab_name}-before-last.png")
                os.rename(last_path, before_last_path)
            self.screenshoter.take_full_screen_screenshot(f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}", last_path)

    def collect_data(self):
        print("#############################################")
        print(f"Monitoring {len(self.stock_names)} stocks...", flush=True)
        start = time()
        current_data = {}
        for i, stock_name in enumerate(self.stock_names):
            if i % int(0.25 * len(self.stock_names)) == 0:
                print(
                    f"\t- Progress {100 * i // len(self.stock_names):.0f}%, time elapsed {strftime('%H:%M:%S', gmtime(time() - start))}",
                    flush=True)
            try:
                company_dict = get_raw_stock_data(stock_name)
                current_data[stock_name] = flatten_dict(company_dict)
            except Exception as e:
                print(f"\t  ! Error while reading data from '{stock_name}'.. skipping !")
        print(f"    - Data collected in {strftime('%H:%M:%S', gmtime(time() - start))}", flush=True)

        # filter out ignore fields data
        current_data = {k: v for k, v in current_data.items() if k not in self.ignore_fields}

        return current_data

    def _analyze_changes(self, changes):
        """"""
        time_str = str(datetime.datetime.now()).replace(" ", "_").replace(":", '-').split(".")[0]
        strings_to_write = []
        for stock_name in changes:
            if stock_name in changes and changes[stock_name]:
                # prepare log lines
                strings_to_write.append(f"Stock: {stock_name}:\n")
                for k, (before, after) in changes[stock_name].items():
                    strings_to_write.append(f"\t- {k}:\n\t\tBefore: {json.dumps(before)}\n\t\tAfter: {json.dumps(after)}\n")

                # screenshot changes
                self.screenhost_stock(stock_name)

        if strings_to_write:
            print("    - ! Changes found !", flush=True)
            f = open(os.path.join(self.output_dir, 'change_logs', f"{time_str}.log"), 'w')
            for string in strings_to_write:
                f.write(string)
            f.close()
        else:
            print("    - No changes found ...", flush=True)

    def run(self):
        if os.path.exists(self.cache_path):
            last_data_entry = pickle.load(open(self.cache_path, 'rb'))
        else:
            last_data_entry = None

        while True:
            current_data = self.collect_data()

            if last_data_entry is not None:
                changes = compare_data_dicts(last_data_entry, current_data)
                self._analyze_changes(changes)

            # last_data_entry.update(current_data)
            last_data_entry = current_data

            pickle.dump(current_data, open(self.cache_path, 'wb'))

            print(f"    - Sleeping for {self.query_freq_minutes} minutes", flush=True)
            sleep(60 * self.query_freq_minutes)


def get_dict_from_url(url):
    req = urllib.request.Request(url)
    page = urllib.request.urlopen(req)
    d = json.loads(page.read().decode('utf-8'))
    return d


def get_raw_stock_data(stock_name):
    # start = time()
    # url = f"https://backend.otcmarkets.com/otcapi/stock/trade/inside/{stock_name}?symbol={stock_name}"
    # price_dict = get_dict_from_url(url)
    # print(f"prices query took {time() - start} seconds")

    # start = time()
    url = f"https://backend.otcmarkets.com/otcapi/company/profile/full/{stock_name}?symbol={stock_name}"
    company_dict = get_dict_from_url(url)
    # print(f"company query took {time() - start} seconds")

    return company_dict


def compare_data_dicts(last_data, current_data):
    changes = {}

    for stock_name, data in current_data.items():
        stock_changes = {}
        for k, v in data.items():
            if stock_name in last_data and k in last_data[stock_name]:
                if last_data[stock_name][k] != v:
                    stock_changes[k] = (last_data[stock_name][k], v)
        changes[stock_name] = stock_changes
    return changes


def flatten_dict(d, parent_key='', sep='_'):
    import collections
    items = []
    for k, v in d.items():
        if type(v) == list:
            v = {str(i): v[i] for i in range(len(v))}
        new_key = parent_key + sep + k if parent_key else k
        if type(v) == dict:
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@Gooey
def main():
    # parser = argparse.ArgumentParser(description='Process some integers.')
    # args = parser.parse_args()
    # args.stock_names_file = 'Stock_Screener.csv'
    # args.query_freq_minutes = 10
    # args.output_dir = 'outputs'
    # args.ignore_file_path = 'ignore_fields.csv'
    # args.chrome_driver = 'chromedriver.exe'

    parser = GooeyParser(description='Process some integers.')
    parser.add_argument('--chrome_driver', default='chromedriver.exe', widget='FileChooser',
                        help='path to chrome driver that allows screen shoting the webside'
                             'download the right version for your browser from https://chromedriver.chromium.org/downloads')
    parser.add_argument('--stock_names_file', default='Stock_Screener.csv',
                        help='A file with a stock name in each file', widget='FileChooser')
    parser.add_argument('--ignore_file_path', default='ignore_fields.csv', widget='FileChooser',
                        help='Fields to ignore while monitoring stocks')

    parser.add_argument('--query_freq_minutes', default=60, widget='IntegerField', type=int,
                        help='How much time to wait between each monitoring iteration')

    parser.add_argument('--output_dir', default='outputs', widget='FileChooser',
                        help="directory to store all this program outputs")

    args = parser.parse_args()

    monitor = StockMonitor(args)
    monitor.run()


if __name__ == '__main__':
    main()
