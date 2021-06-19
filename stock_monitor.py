import pickle
import urllib.request
import json
import os
from time import sleep
import datetime
from shutil import move

from tqdm import tqdm

from screen_shooter import ScreenShooter


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_file_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_file, 'r').readlines()]
        self.output_dir = args.output_dir
        self.screenshoter = ScreenShooter(wait_time=1)
        os.makedirs(os.path.join(args.output_dir, "change_logs"), exist_ok=True)
        os.makedirs(os.path.join(args.output_dir, "status_images"), exist_ok=True)
        self.cache_path = os.path.join(args.output_dir, "monitor_cache.pkl")

        self.screenshoter.wait_time = args.screenshot_wait_time

        if os.path.exists(self.cache_path):
            self.last_data_entry = pickle.load(open(self.cache_path, 'rb'))
        else:
            self.last_data_entry = None

    def screenhost_stock(self, stock_name, force_shot=False):
        """Take a screen shot from the three tabs of this stock page"""
        dirname = os.path.join(self.output_dir, "status_images", stock_name)
        if os.path.exists(dirname) and not force_shot:
            return
        os.makedirs(dirname, exist_ok=True)
        for tab_name in ['profile', 'overview', 'security']:
            last_path = os.path.join(dirname, f"{tab_name}-last.png")
            if os.path.exists(last_path):
                before_last_path = os.path.join(dirname, f"{tab_name}-before-last.png")
                move(last_path, before_last_path)
            self.screenshoter.take_full_screen_screenshot(f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}",
                                                          last_path)

    def collect_stock_data(self, stock_name):
        """Returns a current data dicctionary for each stock loaded from the website servers"""
        try:
            data = StockMonitor.get_raw_stock_data(stock_name)
            data = StockMonitor.flatten_dict(data)
            data = {k: v for k, v in data.items() if k not in self.ignore_fields}
            return data
        except Exception as e:
            return None

    def verify_initial_screenshots(self):
        for stock_name in self.stock_names:
            self.screenhost_stock(stock_name)

    def record_changes(self, changes):
        """Record changes in log files and screenshot sites"""
        lines_to_write = []
        for stock_name in changes:
            if changes[stock_name]:
                # prepare log lines
                lines_to_write.append(f"Stock: {stock_name}:\n")
                for k, (before, after) in changes[stock_name].items():
                    lines_to_write.append(
                        f"\t- {k}:\n\t\tBefore: {json.dumps(before)}\n\t\tAfter: {json.dumps(after)}\n")

                # screenshot changes
                self.screenhost_stock(stock_name, force_shot=True)

        if lines_to_write:
            time_str = str(datetime.datetime.now()).replace(" ", "_").replace(":", '-').split(".")[0]
            log_file = open(os.path.join(self.output_dir, 'change_logs', f"{time_str}.log"), 'w')
            for line in lines_to_write:
                log_file.write(line)

    def save_last_data_to_file(self):
        pickle.dump(self.last_data_entry, open(self.cache_path, 'wb'))

    @staticmethod
    def get_dict_from_url(url):
        req = urllib.request.Request(url)
        page = urllib.request.urlopen(req)
        d = json.loads(page.read().decode('utf-8'))
        return d

    @staticmethod
    def get_raw_stock_data(stock_name):
        # url = f"https://backend.otcmarkets.com/otcapi/stock/trade/inside/{stock_name}?symbol={stock_name}"
        url = f"https://backend.otcmarkets.com/otcapi/company/profile/full/{stock_name}?symbol={stock_name}"
        company_dict = StockMonitor.get_dict_from_url(url)

        return company_dict

    @staticmethod
    def compare_data_dicts(last_data, current_data):
        stock_changes = {}
        if last_data and current_data:
            for k, v in last_data.items():
                if k in current_data and current_data[k] != v:
                    stock_changes[k] = (v, current_data[k])
        return stock_changes

    @staticmethod
    def flatten_dict(d, parent_key='', sep='_'):
        items = []
        for k, v in d.items():
            if type(v) == list:
                v = {str(i): v[i] for i in range(len(v))}
            new_key = parent_key + sep + k if parent_key else k
            if type(v) == dict:
                items.extend(StockMonitor.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
