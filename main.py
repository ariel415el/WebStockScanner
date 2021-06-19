import argparse
from time import sleep

from tqdm import tqdm

from gui import manage_monitor
from stock_monitor import StockMonitor


def drive_monitor_on_cmd(monitor):
    print(f"Verigying base screen shots")
    monitor.verify_initial_screenshots()
    while True:
        current_data = {}
        changes = {}
        pbar = tqdm(monitor.stock_names)
        for stock_name in pbar:
            pbar.set_description(f"{stock_name} Collecting data")
            current_data[stock_name] = monitor.collect_stock_data(stock_name)
            if monitor.last_data_entry is not None:
                changes[stock_name] = StockMonitor.compare_data_dicts(monitor.last_data_entry[stock_name],
                                                                      current_data[stock_name])
        pbar.set_description(f"Comparing data to last entry")
        monitor.last_data_entry = current_data

        monitor.record_changes(changes)
        print(f"Found changes in {sum([1 for x in changes.values() if x])} stocks")

        monitor.save_last_data_to_file()

        print(f"Sleeping for {60 * monitor.query_freq_minutes} seconds")
        sleep(60 * monitor.query_freq_minutes)


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    args = parser.parse_args()
    args.stock_names_file = 'Stock_Screener.csv'
    args.query_freq_minutes = 15
    args.output_dir = 'outputs'
    args.ignore_file_path = 'ignore_fields.csv'
    args.chrome_driver = 'chromedriver.exe'
    args.screenshot_wait_time = 3

    monitor = StockMonitor(args)

    # drive_monitor_on_cmd(monitor)
    manage_monitor(monitor)

if __name__ == '__main__':
    main()