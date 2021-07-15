import json
import os
import urllib.request
from datetime import datetime

from multiprocessing import Process

import numpy as np
import pandas as pd


def plot_csv(dir_path, name='special_fields'):
    import pandas as pd
    import matplotlib.pyplot as plt
    p = os.path.join(dir_path, f"{name}.csv")
    if not os.path.exists(p):
        return
    df = pd.read_csv(p)
    plt.figure(figsize=(10, 10))
    headers = [x for x in df.head()][1:]
    for c in headers:
        plt.plot(df['date'], df[c], label=c)
        plt.grid()
    plt.xticks(rotation=45)
    # ax.yaxis.set_major_formatter(ScalarFormatter())
    plt.legend()
    plt.legend(loc='lower left', bbox_to_anchor=(0.0, 1.0),fancybox=True, shadow=True, ncol=len(headers))
    # plt.tight_layout()
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
    company_dict.update({k:prices_dict[k] for k in ["lastSale", "change", "percentChange", "tickName"]})
    return company_dict


def get_stock_data(stock_name):
    """Returns a current data dicctionary for each stock loaded from the website servers"""
    try:
        data = get_raw_stock_data(stock_name)
        data = flatten_dict(data)
        df = pd.DataFrame.from_dict([data])
        df = df.applymap(str)
        df.replace('', 'Not available', inplace=True)
        return df
    except Exception as e:
        return None

    # manager_names = ['Kevin Booker', 'Kevin durant', 'Micheal Jordan', 'Kobi Bryant', 'Chris Paul', 'R Donoven JR']
    # import random
    # if random.random() > 0.2:
    #     data = {"securities_0_authorizedShares": random.choice([1, 2, 3, 4]),
    #             "securities_0_outstandingShares": random.choice([15, 16, 18, 22]),
    #             "securities_0_restrictedShares": random.choice([12, 13, 45, 667]),
    #             "securities_0_unrestrictedShares": random.choice([555, 666, 777, 888]),
    #             "lastSale": random.choice([0.5, 0.1, 0.7, 0.8]),
    #             "change":random.choice([-0.001, -0.002, 0.005, -0.02]),
    #             "percentChange":random.choice([0.4, 0.6, -0.2, 0.05]),
    #             "tickName":random.choice(['Up', 'Down'])
    #     }
    #     data = pd.DataFrame.from_dict([data])
    #
    # else:
    #     data = None
    # return data


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


def dump_stocks_plot(output_dir, stock_name_list):
    # fields = ["lastSale", "change", "percentChange"]
    df = pd.read_csv(os.path.join(output_dir, "price_status.csv"))
    df = df.loc[df['stock'].isin(stock_name_list)]
    from matplotlib import pyplot as plt

    # ax = df.plot.bar(x='stock', y="percentChange", rot=45, color=(df["percentChange"] > 0).map({True: 'g', False: 'r'}))
    # ax.axhline(y=0, color='k', linestyle='--')
    # ax.set_ylabel("Percentage cahge")

    plt.figure(figsize=(min(len(stock_name_list),20), 5))

    pos_ind, neg_ind = df["percentChange"] > 0, df["percentChange"] <= 0
    pos_rects = plt.bar(df['stock'][pos_ind], df["percentChange"][pos_ind], color='g')
    neg_rects = plt.bar(df['stock'][neg_ind], df["percentChange"][neg_ind], color='r')

    for i, rect in enumerate(pos_rects):
        height = rect.get_height()
        plt.text(rect.get_x() + rect.get_width() / 2., 0.99 * height,
                f"{df['lastSale'][pos_ind].tolist()[i]}$", ha='center', va='bottom')

    for i, rect in enumerate(neg_rects):
        height = rect.get_height()
        plt.text(rect.get_x() + rect.get_width() / 2., 0.99 * height,
                f"{df['lastSale'][neg_ind].tolist()[i]:.4f}$", ha='center', va='top')

    lim = max(abs(df["percentChange"])) * 1.2
    plt.ylim(-lim,lim)

    locs, labels = plt.yticks()
    plt.yticks(ticks=locs, labels=[f'{x:.0f}%' for x in locs])

    plt.xticks(rotation=45)
    plt.grid()
    plot_path = os.path.join(output_dir,"stock_bars.png")
    plt.savefig(plot_path)
    plt.clf()
    return plot_path


def update_plot_fields(csv_path, data_dict, plot_fields):
    if data_dict is None:
        return
    plot_fields_dict = dict()
    for field in plot_fields:
        plot_fields_dict[field] = data_dict[field].values[0] if field in data_dict else 'Not available'
    new_row = pd.DataFrame.from_dict([plot_fields_dict])
    new_row.insert(0, 'date', [get_time_str()])
    new_row.to_csv(csv_path, index=False, header=not os.path.exists(csv_path), mode='a')
    plot_csv_process(os.path.dirname(csv_path))


def update_price_status(log_path, stock_name, stock_data):
    """Updates/adds a row for a given stock in a global file of stocks"""
    header = ["stock", "lastSale", "change", "percentChange"]
    if stock_data is None:
        return
    new_row = [[stock_name] + stock_data[header[1:]].values[0].tolist()]
    if not os.path.exists(log_path):
        new_row = pd.DataFrame(new_row, columns=header)
        new_row.to_csv(log_path, columns=header, index=False)
    else:
        df = pd.read_csv(log_path)
        if any(df['stock'] == stock_name):
            df.loc[df['stock'] == stock_name] = new_row
        else:
            new_row = pd.DataFrame(new_row, columns=header)
            df = df.append(new_row, ignore_index=True)

        df.to_csv(log_path, columns=header, index=False)


def compare_rows(row1, row2):
    if row1 is None or row2 is None:
        return None
    diff = row1 != row2
    diff_where = np.where(diff)
    index = diff.stack()[diff.stack()].index
    if np.any(diff_where):
        diff = pd.DataFrame({'from': row1.values[diff_where], 'to': row2.values[diff_where]}, index=index)
        return diff
    return None