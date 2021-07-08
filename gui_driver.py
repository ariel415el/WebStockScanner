import time
import PySimpleGUI as sg
from time import time
import threading
import datetime

import pandas as pd

import utils
import os
from pathlib import Path

from utils import get_img_data
# sg.theme_previewer()


def t_print(x, end=None):
    time_str = str(datetime.datetime.now()).split(".")[0]
    print(f"{time_str}: {x}", end=end)

def update_changes_log(stocks_with_changes, changes_log_path, max_cols=10):
    # write changes
    new_col = pd.DataFrame(zip([f"{str(datetime.datetime.now()).split('.')[0]}"] + stocks_with_changes))
    if not os.path.exists(changes_log_path):
        new_col.to_csv(changes_log_path, header=False, index=False)
    else:
        df = pd.read_csv(changes_log_path, header=None)
        if df.shape[1] > max_cols:
            df = df.T[-max_cols:].T
        pd.concat([df, new_col], axis=1).to_csv(changes_log_path, header=False, index=False)

def update_status_log(log_path, stock_name, stock_data):
    header = ["stock","lastSale","change", "percentChange", "tickName"]
    if stock_data is None:
        return
    new_row = pd.DataFrame([[stock_name] + [stock_data[k] for k in header[1:]]], columns=header)
    if not os.path.exists(log_path):
        new_row.to_csv(log_path, columns=header, index=False)
    else:
        df = pd.read_csv(log_path)

        if any(df['stock'] == stock_name):
            df.loc[df['stock'] == stock_name] = new_row
        else:
            df = df.append(new_row)

        df.to_csv(log_path, columns=header, index=False)


def verify_initial_data(monitor, window):
    for i, stock_name in enumerate(monitor.stock_names):
        stock_dir_path = os.path.join(monitor.output_dir, "stocks", stock_name)
        if not os.path.exists(stock_dir_path):
            os.makedirs(stock_dir_path, exist_ok=True)
            stock_data = monitor.collect_stock_data(stock_name)
            monitor.save_current_data(stock_name, stock_data)
            monitor.screenshost_stock(stock_name)

        window['PROGRESS_BAR'].update_bar(i)
        window['PROGRESS_TXT'].update(stock_name)


def drive_single_pass(monitor, window):
    # global thread_messages
    stocks_with_changes = []
    t_print("Collecting data")
    for i, stock_name in enumerate(monitor.stock_names):
        stock_data = monitor.collect_stock_data(stock_name)
        update_status_log(os.path.join(monitor.output_dir, "price_status.csv"), stock_name, stock_data)
        if monitor.last_data_entry[stock_name] is not None:
            stock_changes = utils.compare_data_dicts(monitor.last_data_entry[stock_name], stock_data)
            if stock_changes:
                monitor.write_plot_fields_data(stock_name, stock_data)
                monitor.write_changes(stock_name, stock_changes)
                monitor.screenshost_stock(stock_name)

                stocks_with_changes.append(stock_name)
                window['status'].update(f"{str(datetime.datetime.now()).split('.')[0]}: {stock_name}\n" + window['status'].get())

        monitor.save_current_data(stock_name, stock_data)

        window['PROGRESS_BAR'].update_bar(i)
        window['PROGRESS_TXT'].update(stock_name)

    update_changes_log(stocks_with_changes, os.path.join(monitor.output_dir, "changes_log.csv"))
    window['status'].update("########################\n" + window['status'].get())

    t_print(f"Found changes in {len(stocks_with_changes)} stocks")


def get_run_layout(stock_names):
    s = 10
    default_img_path = os.path.join('icons', 'no-img.png')

    img_col1 = sg.Col([
        [sg.Frame('Before-last image',[[ sg.Image(key='status_image_1', filename=default_img_path)]], key='Frame_1')],
        [sg.Frame('Last image', [[sg.Image(key='status_image_2', filename=default_img_path)]], key='Frame_2')]
    ])

    img_col2 = sg.Col([[sg.Frame("Stock graph:", [[sg.Image(key='status_image_0', filename=default_img_path)]], key='Frame_0')]])

    layout = [[sg.Image(filename=os.path.join('icons', 'OTC.png'))],
               [sg.Frame("Log", layout=[[sg.Output(size=(70, s),key='std')]], title_location=sg.TITLE_LOCATION_TOP),
                sg.Frame("Change status", [[sg.Multiline(size=(30, s), key='status')]], title_location=sg.TITLE_LOCATION_TOP),
                sg.Frame("Debug", [[sg.Listbox(values=sorted(list(stock_names)), select_mode=sg.LISTBOX_SELECT_MODE_SINGLE,
                           enable_events=True, size=(10,s), key='-LISTBOX-', default_values=stock_names[0])]],title_location=sg.TITLE_LOCATION_TOP)
                ],
                [img_col1, img_col2],
               [sg.Text(f"Next run in N/A", key='time_to_next_run', size=(15, 1)),
                sg.Drop([0, 1, 5, 10, 30, 60], key='wait_time', default_value=30)],
               [sg.Text('Progress:'), sg.ProgressBar(len(stock_names), size=(20, 20), orientation='h', key='PROGRESS_BAR'),
                sg.Text('', key='PROGRESS_TXT', size=(15, 1))],
               [sg.Button('Run'), sg.Button('Exit')]
              ]

    return layout


def manage_monitor(monitor):
    # global thread_messages
    thread_messages = {'progress': 0, 'progress_txt': '', 'msg': ''}
    timer = time()
    sg.theme('Dark Gray 13')

    # --------------------- Read arguments ---------------------
    # --------------------- Run ---------------------
    layout = get_run_layout(monitor.stock_names)

    window = sg.Window('Multithreaded Window', layout, finalize=True)
    window.read(timeout=1)

    # --------------------- INIT LOOP ---------------------
    t_print(f"Initializing monitor: verigying images for {len(monitor.stock_names)} stocks...", end='')
    thread = threading.Thread(target=verify_initial_data, args=(monitor, window), daemon=True)
    thread.start()
    while thread:
        event, _ = window.read(timeout=100)
        if event == 'Run':
            print("Wait for initialization to finish")

        thread.join(timeout=1)
        if not thread.is_alive():
            window['PROGRESS_BAR'].update_bar(0)  # clear the progress bar
            window['PROGRESS_TXT'].update('')  # clear the progress bar
            thread = None
    print("Done")
    thread = None
    last_status_image = None

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read(timeout=100)
        time_left = datetime.timedelta(seconds=int(values['wait_time'] * 60 - (time() - timer)))
        window['time_to_next_run'].update(f"Next run in {time_left}")

        # Update status image by query
        if values['-LISTBOX-'][0] != last_status_image:
            try_load_images(monitor, window, values['-LISTBOX-'][0])
            last_status_image = values['-LISTBOX-'][0]

        if event in (sg.WIN_CLOSED, 'Exit'):
            break

        # --------------------- Data collecting Thread ---------------------
        # Initiate data collecting thread
        if event == 'Run' or time() - timer > 60 * values['wait_time']:
            if thread is not None:
                t_print("Already running")
            else:
                thread = threading.Thread(target=drive_single_pass, args=(monitor, window), daemon=True)
                thread.start()

        # Terminate data collecting thread
        if thread is not None:
            thread.join(timeout=0)
            if not thread.is_alive():  # the thread finished
                t_print(thread_messages['msg'])
                thread = None
                window['PROGRESS_BAR'].update_bar(0)  # clear the progress bar
                window['PROGRESS_TXT'].update('')  # clear the progress bar
                t_print("Data collecting thread terminated")
            timer = time()

    # if user exits the window, then close the window and exit the GUI func
    window.close()


def open_window():
    layout = [[sg.Text("New Window", key="new")]]
    window = sg.Window("Second Window", layout, modal=True)
    choice = None
    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            break

    window.close()

def try_load_images(monitor, window, stock_name):
    image_paths = [
        ('Stock-graph', os.path.join(monitor.output_dir, "stocks", stock_name, 'special_fields.png'), None, (350, 350))
    ]
    overview_images_dir = os.path.join(monitor.output_dir, "stocks", stock_name, "status_images", 'overview')
    if os.path.exists(overview_images_dir):
        img_paths = sorted(Path(overview_images_dir).iterdir(), key=os.path.getmtime)
        before_last_img_path = last_img_path = None
        if len(img_paths) >= 1:
            last_img_path = img_paths[-1]
        if len(img_paths) > 1:
            before_last_img_path = img_paths[-2]

        image_paths += [
            ('before-last image', before_last_img_path, (0, 275, 1050, 600), (500, 150)),
            ('Last image', last_img_path, (0, 275, 1050, 600), (500, 150)),
        ]

    for i, (name, img_path, crop, maxsize) in enumerate(image_paths):
        if img_path and os.path.exists(img_path):
            # window.Element(f"status_image_{i}").Update(filename=img_path)
            img_data = get_img_data(img_path, first=True, crop=crop, maxsize=maxsize)
            window.Element(f"status_image_{i}").Update(data=img_data)
            date_str = str(datetime.datetime.fromtimestamp(os.path.getmtime(img_path))).split('.')[0]
            window.Element(f"Frame_{i}").Update(f"{name}: {date_str}")

