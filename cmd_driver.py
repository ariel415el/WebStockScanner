import os
import utils
from tqdm import tqdm

def verify_initial_data(monitor):
    tqdm(enumerate(monitor.stock_names))
    for i, stock_name in tqdm:
        stock_dir_path = os.path.join(monitor.output_dir, stock_name)
        if not os.path.exists(stock_dir_path):
            os.makedirs(stock_dir_path, exist_ok=True)
            stock_data = monitor.collect_stock_data(stock_name)
            monitor.save_current_data(stock_name, stock_data)
            monitor.screenshost_stock(stock_name)


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
                changes[stock_name] = utils.compare_data_dicts(monitor.last_data_entry[stock_name],
                                                                      current_data[stock_name])
        pbar.set_description(f"Comparing data to last entry")
        monitor.last_data_entry = current_data

        monitor.record_changes(changes)
        print(f"Found changes in {sum([1 for x in changes.values() if x])} stocks")

        monitor.save_last_data_to_file()

        print(f"Sleeping for {60 * monitor.query_freq_minutes} seconds")
        sleep(60 * monitor.query_freq_minutes)
