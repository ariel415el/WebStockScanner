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
        self.screenshoter = ScreenShooter(wait_time=1)
        self.output_dir = args.output_dir
        self.screenshoter.wait_time = args.screenshot_wait_time

        self.load_cached_data()

    def load_cached_data(self):
        self.last_data_entry = dict()
        for stock_name in self.stock_names:
            cache_path = os.path.join(self.output_dir, stock_name, 'last_entry_cache.pkl')
            if os.path.exists(cache_path):
                self.last_data_entry[stock_name] = pickle.load(open(cache_path, 'rb'))
            else:
                self.last_data_entry[stock_name] = None

    def save_current_data(self, stock_name, stock_data):
        self.last_data_entry[stock_name] = stock_data
        cache_path = os.path.join(self.output_dir, stock_name, 'last_entry_cache.pkl')
        pickle.dump(stock_data, open(cache_path, 'wb'))

        # import pandas as pd
        # csv_path = cache_path.replace(".pkl", ".csv")
        # pd.DataFrame.from_dict({k: [v] for k, v in stock_data.items()}).to_csv(csv_path, mode='a',
        #                                                                header=not os.path.exists(csv_path))

    def screenshost_stock(self, stock_name, force_shot=False):
        """Take a screen shot from the three tabs of this stock page"""
        dirname = os.path.join(self.output_dir, stock_name, "status_images")
        if os.path.exists(dirname) and not force_shot:
            return 0
        os.makedirs(dirname, exist_ok=True)
        ret_val = 0
        for tab_name in ['profile', 'overview', 'security']:
            last_path = os.path.join(dirname, f"{tab_name}-last.png")
            if os.path.exists(last_path):
                before_last_path = os.path.join(dirname, f"{tab_name}-before-last.png")
                move(last_path, before_last_path)
            ret_val += self.screenshoter.take_full_screen_screenshot(
                f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}", last_path)
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

        # manager_names = ['Kevin Booker', 'Kevin durant', 'Micheal Jordan', 'Kobi Bryant', 'Chris Paul', 'R Donoven JR']
        # import numpy as np
        # import random
        # if random.random() > 0.2:
        #     data = {"securities_0_authorizedShares": random.choice([1,2,3,4]),
        #             "securities_0_outstandingShares":  random.choice(manager_names),
        #             "securities_0_restrictedShares": random.choice([12,13,45,667]),
        #             "securities_0_unrestrictedShares": random.choice([555,666,777,888])}
        # else:
        #     data = None
        return data

    def write_changes(self, stock_name, stock_changes):
        """Dumpy changes to log file"""
        if stock_changes:
            time_str = str(datetime.datetime.now()).replace(" ", "_").replace(":", '-').split(".")[0]

            logs_path = os.path.join(self.output_dir, stock_name, 'change_logs')
            os.makedirs(logs_path, exist_ok=True)
            log_file = open(os.path.join(logs_path, f"{time_str}-changes.log"), 'w')

            # prepare log lines
            log_file.write(f"Stock: {stock_name}:\n")
            for k, (before, after) in stock_changes.items():
                log_file.write(f"\t- {k}:\n\t\tBefore: {json.dumps(before)}\n\t\tAfter: {json.dumps(after)}\n")
                # log_file.write(f"\t- {k}:\n\t\tBefore: {before}\n\t\tAfter: {after}\n")

            log_file.close()

    def write_plot_fields_data(self, stock_name, stock_data):
        """Add an entry of current data of the plot fields and update the plot"""
        if stock_data:
            time_str = str(datetime.datetime.now()).replace(" ", "-").split(".")[0]

            output_dir = os.path.join(self.output_dir, stock_name)
            os.makedirs(output_dir, exist_ok=True)
            utils.save_data_csv(stock_data, self.plot_fields, time_str, output_dir)
            utils.plot_csv_process(output_dir)
