import time
import PySimpleGUI as sg
from time import time
import threading
import datetime

import utils
import os
from pathlib import Path

from utils import get_img_data, dump_stocks_plot


def t_print(x, end=None):
    time_str = str(datetime.datetime.now()).split(".")[0]
    print(f"{time_str}: {x}", end=end)


def get_run_layout(stock_names):
    s = 10
    debug_col_1 = sg.Col([[sg.Input(key='input1', size=(10, 1)), sg.Button('Filter', key='filter1')],
                          [sg.Listbox(values=sorted(list(stock_names)), select_mode=sg.LISTBOX_SELECT_MODE_SINGLE,
                                      enable_events=True, size=(10, s), key='list_box1', default_values=stock_names[0]),
                           sg.Button('Show', key='show1')
                           ]])
    debug_col_1 = sg.Frame("Stock Change images", [[debug_col_1]], title_location=sg.TITLE_LOCATION_TOP)

    debug_col_2 = sg.Col([[sg.Input(key='input2', size=(10, 1)), sg.Button('Filter', key='filter2'), sg.Button('All', key='all2'), sg.Button('Clear', key='clr2')],
                          [sg.Listbox(values=sorted(list(stock_names)), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                                      enable_events=True, size=(10, s), key='list_box2', default_values=stock_names[0]),
                           sg.Button('Show', key='show2')]
                          ])
    debug_col_2 = sg.Frame("Prices heatmap", [[debug_col_2]], title_location=sg.TITLE_LOCATION_TOP)
    layout = [[sg.Image(filename=os.path.join('icons', 'OTC.png'))],
              [sg.Frame("Log", layout=[[sg.Output(size=(70, s), key='std')]], title_location=sg.TITLE_LOCATION_TOP),
               sg.Frame("Change status", [[sg.Multiline(size=(30, s), key='status')]],
                        title_location=sg.TITLE_LOCATION_TOP),
               ],
              [debug_col_1, debug_col_2],
              [sg.Text(f"Next run in N/A", key='time_to_next_run', size=(15, 1)), sg.Drop([0, 1, 5, 10, 30, 60], key='wait_time', default_value=30),
               sg.Text(f"Data collecting threads:", size=(17, 1)), sg.Drop([1, 2, 3, 4, 5], key='n_threads', default_value=2),
               # sg.Text(f"Bad reads: 0", key='bad_reads', size=(17, 1)),
               ],

              [sg.Text('Progress:'),
               sg.ProgressBar(len(stock_names), size=(20, 20), orientation='h', key='PROGRESS_BAR'),
               sg.Text('', key='PROGRESS_TXT', size=(20, 1))],
              [sg.Checkbox('Sound-Alarm', True, key='alarm')],
              [sg.Button('Run'), sg.Button('Exit')]
              ]

    return layout


def manage_monitor(monitor):
    # global thread_messages
    timer = time()
    sg.theme('Dark Gray 13')

    # --------------------- Read arguments ---------------------
    # --------------------- Run ---------------------
    layout = get_run_layout(monitor.stock_names)

    window = sg.Window('StockMonitor', layout, finalize=True)
    window.read(timeout=1)

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read(timeout=100)
        time_left = datetime.timedelta(seconds=int(values['wait_time'] * 60 - (time() - timer)))
        window['time_to_next_run'].update(f"Next run in {time_left}")

        # --------------------- Handle gui requests ---------------------

        if event == 'show1':
            show_stock_images(values['list_box1'][0], monitor.output_dir)
        if event == 'show2':
            show_price_changes(values['list_box2'], monitor.output_dir)
        for i in range(1, 3):
            if event == f'filter{i}':
                window[f'list_box{i}'].update(
                    [x for x in monitor.stock_names if values[f'input{i}'] in x])  # display in the listbox
        if event == f'all2':
            window['list_box2'].set_value(monitor.stock_names)
        if event == f'clr2':
            window['list_box2'].set_value([])
        if event in (sg.WIN_CLOSED, 'Exit'):
            break

        # --------------------- Data collecting Threads ---------------------
        # Initiate data collecting thread
        if event == 'Run' or time() - timer > 60 * values['wait_time']:
            if not monitor.collecting_data:
                t_print(f"Starting data collection {values['n_threads']} threads")
                monitor.init_dc_threads(values['n_threads'])
            else:
                t_print("Already running")
        if monitor.collecting_data:
            window['PROGRESS_BAR'].update_bar(monitor.progress)
            window['PROGRESS_TXT'].update(f"{monitor.progress}/{len(monitor.stock_names)}  ({monitor.progress / (time() - timer):.1f} stocks/sec)")
            new_changes = monitor.query_changes()
            if new_changes:
                monitor.add_screenshot_tasks(new_changes)
                new_changes = '\n'.join(new_changes)
                window['status'].update(f"{new_changes}\n" + window['status'].get())
                if values['alarm']:
                    from playsound import playsound
                    playsound(os.path.join('icons', 'icq-uh-oh.mp3'))

            # if not monitor.queue:
            if monitor.is_all_tasks_done():
                monitor.join_dc_threads()
                window['PROGRESS_BAR'].update_bar(0)  # clear the progress bar
                window['PROGRESS_TXT'].update('')
                t_print(f"Data collection Done: \n"
                        f"   - {monitor.num_bad_data_reads} stocks were not read\n"
                        f"   - {len(monitor.changes_list)} stocks changed "
                        f"   - Speed: ({len(monitor.stock_names) / (time() - timer):.1f} stocks/sec)")
                window['status'].update(f"########################\n" + window['status'].get())
                monitor._update_changes_log()
                monitor.reinit_state()
                timer = time()

    # if user exits the window, then close the window and exit the GUI func
    window.close()


def show_price_changes(stock_name_list, output_dir):
    """Dump a plot of price changes of chosen stocks"""
    default_img_path = os.path.join('icons', 'no-img.png')

    layout = [[sg.Image(key='plot', filename=default_img_path)], [sg.Button('Exit')]]
    window = sg.Window("StockMonitor", layout, modal=True, finalize=True)

    plot_path = dump_stocks_plot(output_dir, stock_name_list)
    if os.path.exists(plot_path):
        img_data = get_img_data(plot_path, first=True, maxsize=(1000,1000))
        window.Element(f"plot").Update(data=img_data)
    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            break

    window.close()


def show_stock_images(stock_name, output_dir):
    """Shows before after images and plot fields graph"""
    default_img_path = os.path.join('icons', 'no-img.png')

    img_col1 = sg.Col([
        [sg.Frame('Before-last image', [[sg.Image(key='status_image_1', filename=default_img_path)]], key='Frame_1')],
        [sg.Frame('Last image', [[sg.Image(key='status_image_2', filename=default_img_path)]], key='Frame_2')]
    ])
    img_col2 = sg.Col(
        [[sg.Frame("Stock graph:", [[sg.Image(key='status_image_0', filename=default_img_path)]], key='Frame_0')]])

    layout = [[img_col1, img_col2], [sg.Button('Exit')]]
    window = sg.Window("StockMonitor", layout, modal=True, finalize=True)

    try_load_stock_images(output_dir, window, stock_name)

    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            break

    window.close()


def try_load_stock_images(output_dir, window, stock_name):
    image_paths = [
        ('Stock-graph', os.path.join(output_dir, "stocks", stock_name, 'special_fields.png'), None, (350, 350))
    ]
    overview_images_dir = os.path.join(output_dir, "stocks", stock_name, "status_images", 'overview')
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
