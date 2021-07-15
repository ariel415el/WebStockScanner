import os
import sys
import threading
from collections import deque
from pathlib import Path

import pandas as pd

from screen_shooter import ScreenShooter
import utils
from os.path import join as pjoin

from utils import update_plot_fields, update_price_status, get_stock_data, compare_rows


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_fields_path, 'r').readlines()]
        self.plot_fields = [x.strip() for x in open(args.plot_fields_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_path, 'r').readlines()]
        self.output_dir = args.output_dir

        self.screenshoter = ScreenShooter(10)
        self.screenshoter_lock = threading.Lock()
        self.max_status_images = 10

        self.queue_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.changes_list_lock = threading.Lock()
        self.queue = deque()
        self.changes_list = []

    def run_cycle(self, n_threads=1):
        assert not self.queue
        for stock_name in self.stock_names:
            self._init_folders(stock_name)
            self.queue.append(stock_name)
        pool = []
        for x in range(n_threads):
            name = "Thread_" + str(x)
            t = threading.Thread(name=name, target=motitor_worker, args=(self,))
            t.start()
            pool.append(t)
        for t in pool:
            t.join()

        self._update_changes_log()
        self.changes_list = []

    def pull_task(self):
        self.queue_lock.acquire()
        res = self.queue.pop() if self.queue else None
        self.queue_lock.release()
        return res

    def override_stock_data(self, stock_name, stock_data):
        if stock_data is not None:
            stock_data.to_csv(pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv'), index=False, header=True)

    def get_cached_stock_data(self, stock_name):
        last_data_csv_path = pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv')
        return pd.read_csv(last_data_csv_path, dtype=str) if os.path.exists(last_data_csv_path) else None

    def report_stock_changed(self, stock_name, diff):
        self.changes_list_lock.acquire()
        self.changes_list.append(stock_name)
        self.changes_list_lock.release()

        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs'), exist_ok=True)
        diff.to_csv(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs', f'{utils.get_time_str(for_filename=True)}.csv'))

    def update_plot_fields(self, stock_name, stock_data):
        update_plot_fields(pjoin(self.output_dir, 'stocks', stock_name, 'special_fields.csv'), stock_data, self.plot_fields)

    def update_price_status(self, stock_name, stock_data):
        self.file_lock.acquire()
        update_price_status(pjoin(self.output_dir, "price_status.csv"), stock_name, stock_data)
        self.file_lock.release()

    def screenshost_stock(self, stock_name):
        """Take a screen shot from the three tabs of this stock page"""
        self.screenshoter_lock.acquire()

        ret_val = 0

        for tab_name in ['profile', 'overview', 'security']:
            dirpath = pjoin(self.output_dir, "stocks", stock_name, "status_images", tab_name)
            os.makedirs(dirpath, exist_ok=True)
            time_str = utils.get_time_str(for_filename=True)
            new_file_path = pjoin(dirpath, f"{time_str}.png")
            ret_val += self.screenshoter.take_full_screen_screenshot(f"https://www.otcmarkets.com/stock/{stock_name}/{tab_name}", new_file_path)

            if len(os.listdir(dirpath)) > self.max_status_images:
                oldest_path = min(Path(dirpath).iterdir(), key=os.path.getmtime)
                os.remove(oldest_path)

        self.screenshoter_lock.release()

        return ret_val

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


def motitor_worker(monitor):
    while True:
        stock_name = monitor.pull_task()
        if not stock_name:
            break

        cur_data = monitor.get_cached_stock_data(stock_name)
        new_data = get_stock_data(stock_name)
        monitor.override_stock_data(stock_name, new_data)

        diff = compare_rows(cur_data, new_data)

        stock_changed = diff is not None
        first_time = cur_data is None

        if stock_changed:
            monitor.report_stock_changed(stock_name, diff)

        if stock_changed or first_time:
            utils.update_plot_fields(stock_name, new_data)
            monitor.screenshost_stock(stock_name)

        utils.update_price_status(stock_name, new_data)

    sys.exit()
