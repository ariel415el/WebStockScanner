import os
import sys
import threading
from collections import deque
from pathlib import Path
from time import sleep

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

        self.data_threads_pool = []
        self.queue_lock = threading.Lock()
        self.queue = deque()
        self.file_lock = threading.Lock()
        self.changes_list_lock = threading.Lock()
        self.changes_list = []
        self.progress = 0
        self.last_changes_list = []
        self.collecting_data = False

        self.screenshoter = ScreenShooter(10)
        self.screen_shoting_queue = deque()
        self.screenshoter_lock = threading.Lock()
        self.max_status_images = 20
        self.init_screenshoting_thread()

    def init_dc_threads(self, n_threads):
        self.collecting_data = True

        assert not self.queue
        for stock_name in self.stock_names:
            self._init_folders(stock_name)
            self.queue.append(stock_name)

        for x in range(n_threads):
            name = "Data_Thread_" + str(x)
            t = threading.Thread(name=name, target=data_collection_worker, args=(self,))
            t.start()
            self.data_threads_pool.append(t)

    def is_all_tasks_done(self):
        return self.progress == len(self.stock_names)

    def join_dc_threads(self):
        for t in self.data_threads_pool:
            t.join()
        self.data_threads_pool = []
        self.collecting_data = False
        self.progress = 0

    def run_cycle(self, n_threads=1):
        self.init_dc_threads(n_threads)
        self.join_dc_threads()

        self._update_changes_log()
        self.changes_list = self.last_changes_list = []

    def pull_dc_task(self):
        self.queue_lock.acquire()
        res = self.queue.pop() if self.queue else None
        self.queue_lock.release()
        return res

    def report_dc_task_done(self):
        self.queue_lock.acquire()
        self.progress += 1
        self.queue_lock.release()

    def override_stock_data(self, stock_name, stock_data):
        if stock_data is not None:
            stock_data.to_csv(pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv'), index=False, header=True)

    def get_cached_stock_data(self, stock_name):
        last_data_csv_path = pjoin(self.output_dir, 'stocks', stock_name, 'stock_last_entry_data.csv')
        return pd.read_csv(last_data_csv_path, dtype=str) if os.path.exists(last_data_csv_path) else None

    def query_changes(self):
        # Todo is this slowing us down?
        self.changes_list_lock.acquire()
        new_changes = self.changes_list[len(self.last_changes_list):]
        self.last_changes_list += new_changes
        self.changes_list_lock.release()
        return new_changes

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

    def _init_folders(self, stock_name):
        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'change_logs'), exist_ok=True)
        os.makedirs(pjoin(self.output_dir, 'stocks', stock_name, 'status_images'), exist_ok=True)

    def _update_changes_log(self):
        if self.changes_list:
            csv_path = pjoin(self.output_dir, 'change-log.csv')
            df = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame()
            new_col = pd.DataFrame({utils.get_time_str(): self.changes_list})
            df = pd.concat([new_col, df], axis=1)
            if df.shape[1] > 5:
                df = df.iloc[:, :-1]
            df.to_csv(csv_path, header=True, index=False)

    def screenshost_stock(self, stock_name):
        """Take a screen shot from the three tabs of this stock page"""
        self.screenshoter_lock.acquire()

        ret_val = 0

        for tab_name in ['profile', 'overview', 'security', 'news', 'disclosure']:
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

    def init_screenshoting_thread(self):
        self.screenshit_thread = threading.Thread(name="ScreenShot thread", target=screenshot_worker, args=(self,))
        self.screenshit_thread.start()

    def add_screenshot_tasks(self, stock_names):
        self.screenshoter_lock.acquire()
        self.screen_shoting_queue.extend(stock_names)
        self.screenshoter_lock.release()

    def terminate(self):
        self.screenshoter.terminate()

        self.queue_lock.acquire()
        self.queue = deque()
        self.queue_lock.release()
        self.join_dc_threads()

        self.screenshoter_lock.acquire()
        self.screen_shoting_queue = deque()
        self.screenshoter_lock.release()
        self.screenshit_thread.join()

def data_collection_worker(monitor, screenshot_sites=False):
    while True:
        stock_name = monitor.pull_dc_task()
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
            monitor.update_plot_fields(stock_name, new_data)
            if screenshot_sites:
                monitor.screenshost_stock(stock_name)

        monitor.update_price_status(stock_name, new_data)

        monitor.report_dc_task_done()

    sys.exit()


def screenshot_worker(monitor):
    while True:
        monitor.screenshoter_lock.acquire()
        stock_name = monitor.screen_shoting_queue.pop() if monitor.screen_shoting_queue else None
        monitor.screenshoter_lock.release()

        if stock_name:
            monitor.screenshost_stock(stock_name)
        else:
            sleep(5)
