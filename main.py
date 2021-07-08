import argparse
from time import sleep

from tqdm import tqdm

from gui_driver import manage_monitor
import utils
from stock_monitor import StockMonitor



def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    args = parser.parse_args()
    args.query_freq_minutes = 15
    args.output_dir = 'outputs'
    args.stock_names_path = 'stock_names.csv'
    args.ignore_fields_path = 'ignore_fields.csv'
    args.plot_fields_path = 'plot_fields.csv'
    args.chrome_driver = 'chromedriver.exe'
    args.screenshot_wait_time = 3

    monitor = StockMonitor(args)

    # drive_monitor_on_cmd(monitor)
    manage_monitor(monitor)

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()