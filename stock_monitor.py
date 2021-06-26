import pickle
import json
import os
import datetime
from shutil import move

from screen_shooter import ScreenShooter
import utils


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_fields_path, 'r').readlines()]
        self.plot_fields = [x.strip() for x in open(args.plot_fields_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_path, 'r').readlines()]
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

    def screenshost_stock(self, stock_name, force_shot=False):
        """Take a screen shot from the three tabs of this stock page"""
        dirname = os.path.join(self.output_dir, "status_images", stock_name)
        if os.path.exists(dirname) and not force_shot:
            return 0
        os.makedirs(dirname, exist_ok=True)
        ret_val = 0
        for tab_name in ['profile', 'overview', 'security']:
            last_path = os.path.join(dirname, f"{tab_name}-last.png")
            if os.path.exists(last_path):
                before_last_path = os.path.join(dirname, f"{tab_name}-before-last.png")
                move(last_path, before_last_path)
            ret_val += self.screenshoter.take_full_screen_screenshot(f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}",last_path)
        return ret_val

    def collect_stock_data(self, stock_name):
        """Returns a current data dicctionary for each stock loaded from the website servers"""
        try:
            data = utils.get_raw_stock_data(stock_name)
            data = utils.flatten_dict(data)
            data = {k: v for k, v in data.items() if k not in self.ignore_fields}
            return data
        except Exception as e:
            return None

    def verify_initial_screenshots(self):
        for stock_name in self.stock_names:
            self.screenshost_stock(stock_name)

    def write_changes(self, stock_changes, stock_name):
        """Dumpy changes to log file"""
        if stock_changes:
            time_str = str(datetime.datetime.now()).replace(" ", "_").replace(":", '-').split(".")[0]

            os.makedirs(os.path.join(self.output_dir, 'change_logs', stock_name), exist_ok=True)
            log_file = open(os.path.join(self.output_dir, 'change_logs', stock_name, f"{time_str}-changes.log"), 'w')

            # prepare log lines
            log_file.write(f"Stock: {stock_name}:\n")
            for k, (before, after) in stock_changes.items():
                log_file.write(f"\t- {k}:\n\t\tBefore: {json.dumps(before)}\n\t\tAfter: {json.dumps(after)}\n")

            log_file.close()

    def write_csv(self, stock_data, stock_name):
        """Add an entry of current data of the plot fields and update the plot"""
        if stock_data:
            time_str = str(datetime.datetime.now()).replace(" ", "_").replace(":", '-').split(".")[0]

            output_dir = os.path.join(self.output_dir, 'graphs', stock_name)
            os.makedirs(output_dir, exist_ok=True)
            utils.save_data_csv(stock_data, self.plot_fields, time_str, output_dir)
            utils.plot_csv_process(output_dir)

    def save_last_data_to_file(self):
        pickle.dump(self.last_data_entry, open(self.cache_path, 'wb'))

