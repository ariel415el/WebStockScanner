#!/usr/bin/python3
import time
import PySimpleGUI as sg
from time import time
import threading
import datetime
import utils
import os

from utils import get_img_data


def t_print(x, end=None):
    time_str = str(datetime.datetime.now()).split(".")[0]
    print(f"{time_str}: {x}", end=end)

def drive_single_pass(monitor):
    global thread_messages

    num_changes = 0
    current_data = {}
    t_print("Collecting data")
    for i, stock_name in enumerate(monitor.stock_names):
        current_data[stock_name] = monitor.collect_stock_data(stock_name)

        if monitor.last_data_entry is not None:

            monitor.write_csv(current_data[stock_name], stock_name)

            stock_changes = utils.compare_data_dicts(monitor.last_data_entry[stock_name],
                                                             current_data[stock_name])
            if stock_changes:
                monitor.write_changes(stock_changes, stock_name)
                monitor.screenshost_stock(stock_name, force_shot=True)
                num_changes += 1

        thread_messages['progress'] = i
        thread_messages['progress_txt'] = stock_name
    thread_messages['progress_txt'] = ''
    monitor.last_data_entry = current_data

    thread_messages['msg'] = f"Found changes in {num_changes} stocks"

    monitor.save_last_data_to_file()


def verify_initial_screenshots(monitor):
    global thread_messages
    for i, stock_name in enumerate(monitor.stock_names):
        ret_val = monitor.screenshost_stock(stock_name)
        thread_messages['progress'] = i
        thread_messages['progress_txt'] = f"{stock_name}: {'OK' if ret_val == 0  else str(-1*ret_val) + ' errors'}"

# def read_arguments_layout(time_left, n):
#     layout = [[sg.Text('Machine Learning Command Line Parameters', font=('Helvetica', 16))],
#               [sg.Text('Passes', size=(15, 1)),
#                sg.Spin(values=[i for i in range(1, 1000)], initial_value=20, size=(6, 1)),
#                sg.Text('Steps', size=(18, 1)),
#                sg.Spin(values=[i for i in range(1, 1000)], initial_value=20, size=(6, 1))],
#               [sg.Text('ooa', size=(15, 1)), sg.In(default_text='6', size=(10, 1)), sg.Text('nn', size=(15, 1)),
#                sg.In(default_text='10', size=(10, 1))],
#               [sg.Text('q', size=(15, 1)), sg.In(default_text='ff', size=(10, 1)), sg.Text('ngram', size=(15, 1)),
#                sg.In(default_text='5', size=(10, 1))],
#               [sg.Text('l', size=(15, 1)), sg.In(default_text='0.4', size=(10, 1)), sg.Text('Layers', size=(15, 1)),
#                sg.Drop(values=('BatchNorm', 'other'), auto_size_text=True)],
#               [sg.Text('_' * 100, size=(65, 1))],
#               [sg.Text('Flags', font=('Helvetica', 15), justification='left')],
#               [sg.Checkbox('Normalize', size=(12, 1), default=True), sg.Checkbox('Verbose', size=(20, 1))],
#               [sg.Checkbox('Cluster', size=(12, 1)), sg.Checkbox('Flush Output', size=(20, 1), default=True)],
#               [sg.Checkbox('Write Results', size=(12, 1)), sg.Checkbox('Keep Intermediate Data', size=(20, 1))],
#               [sg.Text('_' * 100, size=(65, 1))],
#               [sg.Text('Loss Functions', font=('Helvetica', 15), justification='left')],
#               [sg.Radio('Cross-Entropy', 'loss', size=(12, 1)),
#                sg.Radio('Logistic', 'loss', default=True, size=(12, 1))],
#               [sg.Radio('Hinge', 'loss', size=(12, 1)), sg.Radio('Huber', 'loss', size=(12, 1))],
#               [sg.Radio('Kullerback', 'loss', size=(12, 1)), sg.Radio('MAE(L1)', 'loss', size=(12, 1))],
#               [sg.Radio('MSE(L2)', 'loss', size=(12, 1)), sg.Radio('MB(L0)', 'loss', size=(12, 1))],
#               [sg.Submit(), sg.Cancel()]]
#
#     return lay


def get_run_layout(stock_names):
    s = 15
    layout = [[sg.Text('Stock monitor log')],
               [sg.Output(size=(70, s)),
                sg.Listbox(values=sorted(list(stock_names)), select_mode=sg.LISTBOX_SELECT_MODE_SINGLE,
                           enable_events=True, size=(10,s), key='-LISTBOX-', default_values=stock_names[0]),
                sg.Frame("Stock graph:", [[sg.Image(key='status_image_0')]], key='Frame_0')
                ],
               [sg.Frame('Before-last image',[[ sg.Image(key='status_image_1')]], key='Frame_1')],
               [sg.Frame('Last image', [[sg.Image(key='status_image_2')]], key='Frame_2')],
               [sg.Text(f"Next run in N/A", key='time_to_next_run', size=(15, 1)),
                sg.Drop([0, 1, 5, 10, 30, 60], key='wait_time', default_value=30)],
               [sg.Text('Progress:'), sg.ProgressBar(len(stock_names), size=(20, 20), orientation='h', key='PROGRESS_BAR'),
                sg.Text('', key='PROGRESS_TXT', size=(15, 1))],
               [sg.Button('Run'), sg.Button('Exit')]
              ]

    return layout


def manage_monitor(monitor):
    global thread_messages
    thread_messages = {'progress': 0, 'progress_txt': '', 'msg': ''}
    timer = time()
    sg.theme('Light Brown 3')

    # --------------------- Read arguments ---------------------
    # --------------------- Run ---------------------
    layout = get_run_layout(monitor.stock_names)

    window = sg.Window('Multithreaded Window', layout)
    window.read(timeout=1)

    # --------------------- INIT LOOP ---------------------
    t_print(f"Initializing monitor: verigying images for {len(monitor.stock_names)} stocks...", end='')
    thread = threading.Thread(target=verify_initial_screenshots, args=(monitor,), daemon=True)
    thread.start()
    while thread:
        window.read(timeout=1)
        window['PROGRESS_BAR'].update_bar(thread_messages['progress'])
        window['PROGRESS_TXT'].update(f"{thread_messages['progress_txt']}")
        thread.join(timeout=1)
        if not thread.is_alive():
            thread_messages = {'progress': 0, 'progress_txt': '', 'msg': ''}
            thread_messages['progress'] = 0
            window['PROGRESS_BAR'].update_bar(0)  # clear the progress bar
            thread = None
    print("Done")

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
                thread = threading.Thread(target=drive_single_pass, args=(monitor,), daemon=True)
                thread.start()

        # Terminate data collecting thread
        if thread is not None:
            window['PROGRESS_BAR'].update_bar(thread_messages['progress'])
            window['PROGRESS_TXT'].update(f"{thread_messages['progress_txt']}")

            thread.join(timeout=0)
            if not thread.is_alive():  # the thread finished
                t_print(thread_messages['msg'])
                thread = None
                thread_messages['progress'] = 0
                window['PROGRESS_BAR'].update_bar(0)  # clear the progress bar
                t_print("Data collecting thread terminated")
            timer = time()

    # if user exits the window, then close the window and exit the GUI func
    window.close()


def try_load_images(monitor, window, stock_name):
    image_paths = [
        ('Stock-graph', os.path.join(monitor.output_dir, "graphs", stock_name, 'data.png'), None, (250, 250)),
        ('before-last image', os.path.join(monitor.output_dir, "status_images", stock_name, 'overview-before-last.png'), (0, 275, 1050, 600), (800, 200)),
        ('Last image', os.path.join(monitor.output_dir, "status_images", stock_name, 'overview-last.png'), (0, 275, 1050, 600), (800, 200)),
    ]

    for i, (name, img_path, crop, maxsize) in enumerate(image_paths):
        if os.path.exists(img_path):
            img_data = get_img_data(img_path, first=True, crop=crop, maxsize=maxsize)
            window.Element(f"status_image_{i}").Update(data=img_data)
            date_str = str(datetime.datetime.fromtimestamp(os.path.getmtime(img_path))).split('.')[0]
            window.Element(f"Frame_{i}").Update(f"{name}: {date_str}")

