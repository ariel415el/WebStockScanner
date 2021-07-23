import os
import sys
import threading
from collections import deque
from pathlib import Path
from time import sleep

import pandas as pd

from screen_shooter import ScreenShooter
from os.path import join as pjoin
from datetime import datetime
import utils
import heapq


class TaskQueue:
    def __init__(self, starting_values):
        self.lock = threading.Lock()
        self.heap = starting_values
        heapq.heapify(self.heap)

    def push(self, value):
        self.lock.acquire()
        heapq.heappush(self.heap, value)
        self.lock.release()

    def pop(self):
        self.lock.acquire()
        if not self.heap:
            return None
        task = heapq.heappop(self.heap)
        self.lock.release()
        return task

    def is_empty(self):
        self.lock.acquire()
        res = not bool(self.heap)
        self.lock.release()
        return res

    def clear(self):
        self.lock.acquire()
        self.heap = []
        self.lock.release()

class Stockdata:
    def __init__(self, stock_name, outputs_dir):
        self.name = stock_name
        self.outputs_dir = outputs_dir

        self.data = None
        self.data_last_modification_date = None
        self.cache_path = pjoin(self.outputs_dir, 'stock_last_entry_data.csv')
        if os.path.exists(self.cache_path):
            self.data = pd.read_csv(self.cache_path, dtype=str)
            self.data_last_modification_date = datetime.fromtimestamp(Path(self.cache_path).stat().st_mtime)

        self.num_bad_data_reads = 0

        self.logs_dir = pjoin(self.outputs_dir, 'change_logs')
        self.screen_shots_dir = pjoin(self.outputs_dir, 'status_images')
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.screen_shots_dir, exist_ok=True)
        self.special_fields_file = pjoin(self.outputs_dir, 'special_fields.csv')

    def set_data(self, data):
        self.data_last_modification_date = datetime.now()
        if data is not None:
            self.data = data
            self.data.to_csv(self.cache_path, index=False, header=True)

    def write_changes(self, diff):
        diff.to_csv(pjoin(self.logs_dir, f'{utils.get_time_str(for_filename=True)}.csv'))

    def update_plot_fields(self, plot_fields):
        utils.update_plot_fields(self.special_fields_file, self.data, plot_fields)

    def report_bad_data_read(self):
        self.data_last_modification_date = datetime.now()
        self.num_bad_data_reads += 1

    def __lt__(self, other):
        if self.data_last_modification_date is None:
            return True
        elif other.data_last_modification_date is None:
            return False
        return self.data_last_modification_date < other.data_last_modification_date


class StockMonitor:
    def __init__(self, args):
        self.query_freq_minutes = args.query_freq_minutes
        self.ignore_fields = [x.strip() for x in open(args.ignore_fields_path, 'r').readlines()]
        self.plot_fields = [x.strip() for x in open(args.plot_fields_path, 'r').readlines()]
        self.stock_names = [x.strip() for x in open(args.stock_names_path, 'r').readlines()]
        self.output_dir = args.output_dir

        self.collecting_data = False

        self.data_threads_pool = []
        self.task_queue = TaskQueue([])

        self.changes_list_lock = threading.Lock()
        self.changes_list = []
        self.last_changes_list = []

        self.file_lock = threading.Lock()

        self.status_lock = threading.Lock()
        self.progress = 0
        self.num_bad_data_reads = 0

        self.screenshoter = ScreenShooter(10)
        self.screen_shoting_queue = deque()
        self.screenshoter_lock = threading.Lock()
        self.max_status_images = 20
        self.init_screenshoting_thread()

    def init_dc_threads(self, n_threads):
        self.collecting_data = True

        assert self.task_queue.is_empty()
        for stock_name in self.stock_names:
            task = Stockdata(stock_name, pjoin(self.output_dir, 'stocks', stock_name))
            self.task_queue.push(task)

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

    def reinit_state(self):
        self.data_threads_pool = []
        self.changes_list = []
        self.collecting_data = False
        self.progress = 0
        self.num_bad_data_reads = 0

    def run_cycle(self, n_threads=1):
        self.init_dc_threads(n_threads)
        self.join_dc_threads()

        self._update_changes_log()
        self.changes_list = self.last_changes_list = []

    def query_changes(self):
        # Todo is this slowing us down?
        self.changes_list_lock.acquire()
        new_changes = self.changes_list[len(self.last_changes_list):]
        self.last_changes_list += new_changes
        self.changes_list_lock.release()
        return new_changes

    def report_stock_changed(self, stock_name):
        self.changes_list_lock.acquire()
        self.changes_list.append(stock_name)
        self.changes_list_lock.release()

    def update_price_status(self, stock_name, stock_data):
        self.file_lock.acquire()
        utils.update_price_status(pjoin(self.output_dir, "price_status.csv"), stock_name, stock_data)
        self.file_lock.release()

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

    def report_bad_data_read(self):
        self.status_lock.acquire()
        self.num_bad_data_reads += 1
        self.progress += 1
        self.status_lock.release()

    def report_dc_task_done(self):
        self.status_lock.acquire()
        self.progress += 1
        self.status_lock.release()

    def get_status(self):
        self.status_lock.acquire()
        progress, bad_reads = self.progress, self.num_bad_data_reads
        self.status_lock.release()
        return progress, bad_reads

    def terminate(self):
        self.screenshoter.terminate()

        self.task_queue.clear()
        self.join_dc_threads()

        self.screenshoter_lock.acquire()
        self.screen_shoting_queue = deque()
        self.screenshoter_lock.release()
        self.screenshit_thread.join()


def data_collection_worker(monitor, screenshot_sites=False):
    while not monitor.task_queue.is_empty():
        task = monitor.task_queue.pop()

        cur_data = task.data
        new_data = utils.get_stock_data(task.name)
        if new_data is None:
            task.report_bad_data_read()
            if task.num_bad_data_reads > 3:
                print(f"{threading.currentThread().getName()}: Skipping {task.name}. It couldn't be read for {task.num_bad_data_reads} times")
                monitor.report_bad_data_read()
            else:
                print(f"{threading.currentThread().getName()}: {task.name}  couldn't be read for {task.num_bad_data_reads} times,"
                      f" sleeping for {5} seconds")
                sleep(5)
                monitor.task_queue.push(task)
            continue

        task.set_data(new_data)
        diff = utils.compare_rows(cur_data, new_data, monitor.ignore_fields)

        stock_changed = diff is not None
        first_time = cur_data is None

        if stock_changed:
            task.write_changes(diff)
            monitor.report_stock_changed(task.name)

        if stock_changed or first_time:
            task.update_plot_fields(monitor.plot_fields)
            if screenshot_sites:
                monitor.screenshost_stock(task.name)

        monitor.update_price_status(task.name, new_data)

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
