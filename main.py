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
    args.stock_names_path = 'csvs\stock_names.csv'
    args.ignore_fields_path = 'csvs\ignore_fields.csv'
    args.plot_fields_path = 'csvs\plot_fields.csv'
    args.chrome_driver = 'chromedriver.exe'
    args.screenshot_wait_time = 3

    monitor = StockMonitor(args)
    while True:
        print("Starting cycle")
        monitor.run_cycle(1)
        print("Cycle done sleepnig..")
        sleep(4)
    # drive_monitor_on_cmd(monitor)
    # manage_monitor(monitor)

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()