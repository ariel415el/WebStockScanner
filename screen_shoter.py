from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import numpy as np
from io import BytesIO
from PIL import Image


class ScreenShoter:
    def __init__(self, top_crop=0, bottom_crop=0, zoom=1.0):
        self.driver = webdriver.Chrome('chromedriver.exe')
        self.driver.set_page_load_timeout(10)
        self.driver.set_window_size(1000, 1000)
        self.driver.minimize_window()
        self.top_crop = top_crop
        self.bottom_crop = bottom_crop
        self.zoom = zoom

    def take_screenshot(self, url, save_path):
        try:
            self.driver.get(url)
            # wait for stock prise to be available
            WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.NAME, 'h2')))
        except TimeoutException:
            self.driver.execute_script("window.stop();")
        self.driver.execute_script(f"document.body.style.zoom='{int(self.zoom*100)}%'")

        bytes = self.driver.get_screenshot_as_png()
        self.driver.minimize_window()

        img = np.array(Image.open(BytesIO(bytes)))[:, :, :3]

        top_crop = int(self.top_crop*img.shape[0]) if self.top_crop != 0 else 0
        bottom_crop = int(self.bottom_crop*img.shape[0]) if self.bottom_crop != 0 else -1
        img = img[top_crop: bottom_crop]

        Image.fromarray(img).save(save_path)

