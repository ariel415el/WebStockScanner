import os
import ast
from time import strftime, gmtime, time, sleep
from selenium import webdriver
from bs4 import BeautifulSoup


from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

main_site = "https://www.otcmarkets.com/stock/"
stocks = ["OZSC/overview", "KYNC/overview", "NUUU/overview", "INTK/overview", "HVCW/overview"]
log_path = 'log_stocks.txt'
query_frequency_minutes = 10
delim = "_#_"

driver = webdriver.Chrome('/home/ariel/Downloads/chromedriver_linux64/chromedriver')


driver.set_page_load_timeout(10)


def get_bs(url):
    try:
        driver.get(url)
        # wait for stock prise to be available
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, 'h2')))
    except TimeoutException:
        driver.execute_script("window.stop();")
    bs = BeautifulSoup(driver.page_source, 'html.parser')  # using the default html parser
    return bs

def extract_stock_data(bs):
    stock_price = float(bs.find_all("h2")[0].contents[0])

    return {"stock_price": stock_price}


def main():
    if os.path.exists(log_path):
        last_data_entry = open(log_path, 'r').readlines()[-1]
        last_data_entry = ast.literal_eval(last_data_entry.split(delim)[-1])
    else:
        last_data_entry = None

    while True:
        start = time()
        current_data = dict()
        is_changed = False
        for stock in stocks:
            bs = get_bs(main_site + stock)
            current_data[stock] = extract_stock_data(bs)
            if last_data_entry and last_data_entry[stock] != current_data[stock]:
                is_changed = True

        pc_time = strftime("(%Y-%m-%d-%H:%M:%S)", gmtime())
        driver.get_screenshot_as_file(f"imgs/{pc_time}.png")
        log = f"{pc_time}{delim}{is_changed}{delim}{current_data}"
        print(log)
        f = open(log_path, 'a')
        f.write(f"{log}\n")
        f.close()
        print(f"queries/sec {len(stocks) / (time() - start)}")
        sleep(60 * query_frequency_minutes)

if __name__ == '__main__':
    main()