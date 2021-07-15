import datetime
import json
import os
import sys
import threading
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from queue import Queue

from screen_shooter import ScreenShooter
import utils
from os.path import join as pjoin


def update_plot_fields(csv_path, data_dict, plot_fields):
    if data_dict is None:
        return
    plot_fields_dict = dict()
    for field in plot_fields:
        plot_fields_dict[field] = data_dict[field].values[0] if field in data_dict else 'Not available'
    new_row = pd.DataFrame.from_dict([plot_fields_dict])
    new_row.insert(0, 'date', [utils.get_time_str()])
    new_row.to_csv(csv_path, index=False, header=not os.path.exists(csv_path), mode='a')


def update_prices_status(log_path, stock_name, stock_data):
    """Updates/adds a row for a given stock in a global file of stocks"""
    header = ["stock", "lastSale", "change", "percentChange"]
    if stock_data is None:
        return
    new_row = [[stock_name] + stock_data[header[1:]].values[0].tolist()]
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


def collect_stock_data(stock_name):
    """Returns a current data dicctionary for each stock loaded from the website servers"""
    try:
        data = utils.get_raw_stock_data(stock_name)
        data = utils.flatten_dict(data)
        df = pd.DataFrame.from_dict([data])
        df = df.applymap(str)
        # df.replace('', 'N/A', inplace=True)
        df.replace('', 'Not available', inplace=True)
        return df
    except Exception as e:
        return None

    # manager_names = ['Kevin Booker', 'Kevin durant', 'Micheal Jordan', 'Kobi Bryant', 'Chris Paul', 'R Donoven JR']
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
    #     data = pd.DataFrame.from_dict([data])
    #
    # else:
    #     data = None
    # return data


def compare_rows(row1, row2):
    if row1 is None or row2 is None:
        return None
    diff = row1 != row2
    diff_where = np.where(diff)
    index = diff.stack()[diff.stack()].index
    if np.any(diff_where):
        diff = pd.DataFrame({'from': row1.values[diff_where], 'to': row2.values[diff_where]}, index=index)
        return diff
    return None


def worker(monitor):
    while True:
        stock_name = monitor.pull_task()
        if not stock_name:
            break

        cur_data = monitor.get_stock_data(stock_name)
        new_data = collect_stock_data(stock_name)
        monitor.override_stock_data(stock_name, new_data)

        diff = compare_rows(cur_data, new_data)

        if diff is not None:
            monitor.report_stock_changed(stock_name, diff)
            monitor.update_plot_fields(stock_name, new_data)
        elif cur_data is None:
            monitor.update_plot_fields(stock_name, new_data)

        monitor.update_price_status(stock_name, new_data)

    sys.exit()


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_fields_path, 'r').readlines()]
        self.plot_fields = [x.strip() for x in open(args.plot_fields_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_path, 'r').readlines()]
        self.output_dir = args.output_dir

        self.queue_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.changes_list_lock = threading.Lock()
        self.queue = deque()
        self.changes_list = []

    def report_stock_changed(self, stock_name, diff):
        self.changes_list_lock.acquire()
        self.changes_list.append(stock_name)
        self.changes_list_lock.release()

        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs'), exist_ok=True)
        diff.to_csv(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs', f'{utils.get_time_str(for_filename=True)}.csv'))

    def override_stock_data(self, stock_name, stock_data):
        if stock_data is not None:
            stock_data.to_csv(pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv'), index=False, header=True)

    def update_plot_fields(self, stock_name, stock_data):
        update_plot_fields(pjoin(self.output_dir, 'stocks', stock_name, 'special_fields.csv'), stock_data, self.plot_fields)

    def update_price_status(self, stock_name, stock_data):
        self.file_lock.acquire()
        update_prices_status(pjoin(self.output_dir, "price_status.csv"), stock_name, stock_data)
        self.file_lock.release()

    def pull_task(self):
        self.queue_lock.acquire()
        res = self.queue.pop() if self.queue else None
        self.queue_lock.release()
        return res

    def get_stock_data(self, stock_name):
        last_data_csv_path = pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv')
        return pd.read_csv(last_data_csv_path, dtype=str) if os.path.exists(last_data_csv_path) else None

    def _update_changes_log(self):
        print(f"Stock changed: {self.changes_list}")
        if self.changes_list:
            csv_path = pjoin(self.output_dir, 'change-log.csv')
            df = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame()
            new_col = pd.DataFrame({utils.get_time_str(): self.changes_list})
            df = pd.concat([new_col, df], axis=1)
            if df.shape[1] > 5:
                df = df.iloc[:, :-1]
            df.to_csv(csv_path, header=True, index=False)

    def _init_folders(self, stock_name):
        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs'), exist_ok=True)
        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'status_images'), exist_ok=True)

    def run_cycle(self, n_threads=1):
        assert not self.queue
        for stock_name in self.stock_names:
            self._init_folders(stock_name)
            self.queue.append(stock_name)
        pool = []
        for x in range(n_threads):
            name = "Thread_" + str(x)
            t = threading.Thread(name=name, target=worker, args=(self,))
            t.start()
            pool.append(t)
        for t in pool:
            t.join()

        self._update_changes_log()
        self.changes_list = []


    def screenshost_stock(self, stock_name):
        """Take a screen shot from the three tabs of this stock page"""

        ret_val = 0

        for tab_name in ['profile', 'overview', 'security']:
            dirpath = pjoin(self.output_dir, "stocks", stock_name, "status_images", tab_name)
            os.makedirs(dirpath, exist_ok=True)
            time_str = utils.get_time_str(for_filename=True)
            new_file_path = pjoin(dirpath, f"{time_str}.png")
            ret_val += self.screenshoter.take_full_screen_screenshot(
                f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}", new_file_path)

            if len(os.listdir(dirpath)) > self.max_status_images:
                oldest_path = min(Path(dirpath).iterdir(), key=os.path.getmtime)
                os.remove(oldest_path)

        return ret_val


    # def write_plot_fields_data(self, stock_name, stock_data):
    #     """Add an entry of current data of the plot fields and update the plot"""
    #     if stock_data:
    #         time_str = utils.get_time_str(for_filename=False)
    #
    #         output_dir = pjoin(self.output_dir, "stocks", stock_name)
    #         os.makedirs(output_dir, exist_ok=True)
    #         utils.save_data_csv(stock_data, self.plot_fields, time_str, output_dir)
    #         utils.plot_csv_process(output_dir)

