import json
import os
import urllib.request
from datetime import datetime

from multiprocessing import Process


def save_data_csv(data, plot_fields, time_str, output_dir, name='special_fields'):
    """Save specified entries from a data dictionary to a csv and plot the cahnge over time"""
    for field in plot_fields:
        if field not in data:
            print(f"Error: Field: {field} is not part of the data dictionary")
            return
    f_path = os.path.join(output_dir, f"{name}.csv")
    if not os.path.exists(f_path):
        f = open(f_path, 'w')
        f.write(",".join(['date'] + [field.replace('securities_0_', '') for field in plot_fields]) + "\n")
    else:
        f = open(f_path, 'a')
    f.write(",".join([time_str] + [str(data[field]) for field in plot_fields]) + '\n')
    f.close()


def plot_csv(dir_path, name='special_fields'):
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter
    p = os.path.join(dir_path, f"{name}.csv")
    if not os.path.exists(p):
        return
    df = pd.read_csv(p)
    plt.figure(figsize=(10, 10))
    headers = [x for x in df.head()][1:]
    for c in headers:
        plt.plot(df['date'], df[c], label=c)
        # plt.gcf().autofmt_xdate()
        plt.grid()
    plt.xticks(rotation=45)
    # ax.yaxis.set_major_formatter(ScalarFormatter())
    plt.legend()
    plt.legend(loc='lower left', bbox_to_anchor=(0.0, 1.0),fancybox=True, shadow=True, ncol=len(headers))
    # plt.grid()
    plt.tight_layout()
    # ax = plt.gca()
    # ax.yaxis.set_major_formatter(ScalarFormatter())
    plt.savefig(os.path.join(dir_path, f"{name}.png"))
    plt.clf()


def plot_csv_process(dir_path):
    p = Process(target=plot_csv, args=(dir_path,))
    p.start()
    p.join()


def get_dict_from_url(url):
    req = urllib.request.Request(url)
    page = urllib.request.urlopen(req)
    d = json.loads(page.read().decode('utf-8'))
    return d


def get_raw_stock_data(stock_name):
    url = f"https://backend.otcmarkets.com/otcapi/stock/trade/inside/{stock_name}?symbol={stock_name}"
    prices_dict = get_dict_from_url(url)
    url = f"https://backend.otcmarkets.com/otcapi/company/profile/full/{stock_name}?symbol={stock_name}"
    company_dict = get_dict_from_url(url)
    company_dict.update({k:prices_dict[k] for k in ["lastSale","change", "percentChange", "tickName"]})
    return company_dict


def compare_data_dicts(last_data, current_data):
    """Return a dictionary with all changes between two dictionaries"""
    stock_changes = {}
    if last_data and current_data:
        for k, v in last_data.items():
            if k in current_data and current_data[k] != v:
                stock_changes[k] = (v, current_data[k])
    return stock_changes


def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        if type(v) == list:
            v = {str(i): v[i] for i in range(len(v))}
        new_key = parent_key + sep + k if parent_key else k
        if type(v) == dict:
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_img_data(f, maxsize=(200, 200), first=False, crop=None):
    """Generate image data using PIL
    """
    from PIL import Image, ImageTk
    import io
    img = Image.open(f)
    if crop:
        img = img.crop(crop)
    img.thumbnail(maxsize)
    if first:                     # tkinter is inactive the first time
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        del img
        return bio.getvalue()
    return ImageTk.PhotoImage(img)


def get_time_str(for_filename=True):
    t = datetime.now()
    if for_filename:
        time_str = str(t).replace(" ", "_").replace(":", '-').split(".")[0]
    else:
        time_str = str(t).replace(" ", "-").split(".")[0]
    return time_str
