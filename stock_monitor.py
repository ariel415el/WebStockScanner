import datetime
import pickle
import json
import os
from pathlib import Path

import pandas as pd

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
        self.max_status_images = 10
        self.load_cached_data()

    def load_cached_data(self):
        self.last_data_entry = dict()
        for stock_name in self.stock_names:
            cache_path = os.path.join(self.output_dir, "stocks", stock_name, 'last_entry_cache.pkl')
            if os.path.exists(cache_path):
                self.last_data_entry[stock_name] = pickle.load(open(cache_path, 'rb'))
            else:
                self.last_data_entry[stock_name] = None

    def pickle_entire_stock_data(self, stock_name, stock_data):
        # pickle entire data
        self.last_data_entry[stock_name] = stock_data
        cache_path = os.path.join(self.output_dir, "stocks", stock_name, 'last_entry_cache.pkl')
        pickle.dump(stock_data, open(cache_path, 'wb'))

    def screenshost_stock(self, stock_name):
        """Take a screen shot from the three tabs of this stock page"""

        ret_val = 0

        for tab_name in ['profile', 'overview', 'security']:
            dirpath = os.path.join(self.output_dir, "stocks", stock_name, "status_images", tab_name)
            os.makedirs(dirpath, exist_ok=True)
            time_str = utils.get_time_str(for_filename=True)
            new_file_path = os.path.join(dirpath, f"{time_str}.png")
            ret_val += self.screenshoter.take_full_screen_screenshot(
                f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}", new_file_path)

            if len(os.listdir(dirpath)) > self.max_status_images:
                oldest_path = min(Path(dirpath).iterdir(), key=os.path.getmtime)
                os.remove(oldest_path)

        return ret_val

    def collect_stock_data(self, stock_name):
        """Returns a current data dicctionary for each stock loaded from the website servers"""
        try:
            data = utils.get_raw_stock_data(stock_name)
            data = utils.flatten_dict(data)
            # data = {k: v for k, v in data.items() if k not in self.ignore_fields}
            return data
        except Exception as e:
            return None

        # # manager_names = ['Kevin Booker', 'Kevin durant', 'Micheal Jordan', 'Kobi Bryant', 'Chris Paul', 'R Donoven JR']
        # import random
        # if random.random() > 0.2:
        #     data = {"securities_0_authorizedShares": random.choice([1, 2, 3, 4]),
        #             "securities_0_outstandingShares": random.choice([15, 16, 18, 22]),
        #             "securities_0_restrictedShares": random.choice([12, 13, 45, 667]),
        #             "securities_0_unrestrictedShares": random.choice([555, 666, 777, 888]),
        #             "lastSale": random.choice([0.5, 0.1, 0.7, 0.8]),
        #             "change":random.choice([-0.001, -0.002, 0.005, -0.02]),
        #             "percentChange":random.choice([0.4, 0.6, -0.2, 0.05]),
        #             "tickName":random.choice(['Up', 'Down'])
        #     }
        # else:
        #     data = None
        # return data

    def write_changes(self, stock_name, stock_changes):
        """Dumpy changes to log file"""
        if stock_changes:
            time_str = utils.get_time_str(for_filename=True)

            logs_path = os.path.join(self.output_dir, "stocks", stock_name, 'change_logs')
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
            time_str = utils.get_time_str(for_filename=False)

            output_dir = os.path.join(self.output_dir, "stocks", stock_name)
            os.makedirs(output_dir, exist_ok=True)
            utils.save_data_csv(stock_data, self.plot_fields, time_str, output_dir)
            utils.plot_csv_process(output_dir)

    def update_prices_status(self, stock_name, stock_data):
        """Updates/adds a row for a given stock in a global file of stocks"""
        log_path = os.path.join(self.output_dir, "price_status.csv")
        header = ["stock", "lastSale", "change", "percentChange"]
        if stock_data is None:
            return
        new_row = [[stock_name] + [stock_data[k] for k in header[1:]]]
        if not os.path.exists(log_path):
            new_row = pd.DataFrame(new_row, columns=header)
            new_row.to_csv(log_path, columns=header, index=False)
        else:
            df = pd.read_csv(log_path)
            if any(df['stock'] == stock_name):
                df.loc[df['stock'] == stock_name] = new_row
            else:
                new_row = pd.DataFrame(new_row, columns=header)
                df = df.append(new_row, ignore_index=True)

            df.to_csv(log_path, columns=header, index=False)