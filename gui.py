#!/usr/bin/python3
import time
import PySimpleGUI as sg
from time import time
from multiprocessing import Process
import threading
import datetime
from stock_monitor import StockMonitor


def long_operation_thread(monitor):
    global thread_message, thread_progress, thread_progress_txt

    current_data = {}
    changes = {}
    for i, stock_name in enumerate(monitor.stock_names):
        current_data[stock_name] = monitor.collect_stock_data(stock_name)
        if monitor.last_data_entry is not None:
            changes[stock_name] = StockMonitor.compare_data_dicts(monitor.last_data_entry[stock_name],
                                                                  current_data[stock_name])
        thread_progress = i
        thread_progress_txt = stock_name
    thread_progress_txt = ''
    monitor.last_data_entry = current_data

    monitor.record_changes(changes)
    thread_message = f"Found changes in {sum([1 for x in changes.values() if x])} stocks"

    monitor.save_last_data_to_file()


def manage_monitor(monitor):
    global thread_message, thread_progress, thread_progress_txt
    thread_message = thread_progress_txt = ''
    thread_progress = 0
    timer = time()
    sg.theme('Light Brown 3')
    time_left = datetime.timedelta(seconds=30*60 - (time() - timer))
    layout = [[sg.Text('Stock monitor log')],
              [sg.Output(size=(70, 12))],
              [sg.Text(f"Next run in {time_left}", key='time_to_next_run', size=(15,1)), sg.Drop([0, 1, 5, 10, 30, 60], key='wait_time', default_value=30)],
              [sg.Text('Progress:'), sg.ProgressBar(len(monitor.stock_names), size=(20, 20), orientation='h', key='-PROG-'), sg.Text('', key='progress_msg', size=(5,1))],
              [sg.Button('Run'), sg.Button('Exit')]
              ]

    window = sg.Window('Multithreaded Window', layout)

    threading.Thread(target=monitor.verify_initial_screenshots, daemon=True).start()

    # --------------------- EVENT LOOP ---------------------
    data_collecting_thread = None
    while True:
        event, values = window.read(timeout=100)
        time_left = datetime.timedelta(seconds=int(values['wait_time'] * 60 - (time() - timer)))
        window['time_to_next_run'].update(f"Next run in {time_left}")
        if event == 'Run' or time() - timer > 60 * values['wait_time']:
            if data_collecting_thread is not None:
                print("Already running")
            else:
                data_collecting_thread = threading.Thread(target=long_operation_thread, args=(monitor,), daemon=True)
                # data_collecting_thread = Process(target=long_operation_thread, args=(monitor, window,), daemon=True)
                data_collecting_thread.start()

        if data_collecting_thread is not None:
            window['-PROG-'].update_bar(thread_progress)
            window['progress_msg'].update(f"{thread_progress_txt}")

            data_collecting_thread.join(timeout=0)
            if not data_collecting_thread.is_alive():  # the thread finished
                print(thread_message)
                data_collecting_thread = None
                thread_progress = 0
                window['-PROG-'].update_bar(thread_progress)  # clear the progress bar
            timer = time()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break

    # if user exits the window, then close the window and exit the GUI func
    window.close()

