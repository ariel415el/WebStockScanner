from selenium import webdriver


class ScreenShooter:
    def __init__(self, wait_time=0):
        options = webdriver.ChromeOptions()
        options.add_argument("--log-level=3")
        options.headless = True
        self.driver = webdriver.Chrome('chromedriver.exe',  options=options)
        self.driver.set_page_load_timeout(wait_time)

    def take_full_screen_screenshot(self, url, save_path):
        try:
            self.driver.get(url)
        except Exception as e:
            return -1

        S = lambda X: self.driver.execute_script('return document.body.parentNode.scroll' + X)
        self.driver.set_window_size(S('Width'), S('Height'))  # May need manual adjustment
        self.driver.find_element_by_tag_name('body').screenshot(save_path)

        return 0

    def terminate(self):
        self.driver.close()