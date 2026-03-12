from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests
import os
import time

def download_first_google_image(topic, save_dir="images"):
    os.makedirs(save_dir, exist_ok=True)

    # Setup Chrome browser
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # run in background
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Open Google Images
        driver.get("https://www.google.com/imghp")
        time.sleep(2)

        # Search for the topic
        search_box = driver.find_element(By.NAME, "q")
        search_box.send_keys(topic)
        search_box.submit()
        time.sleep(3)

        # Get first image thumbnail
        first_img = driver.find_element(By.CSS_SELECTOR, "img.Q4LuWd")
        first_img.click()
        time.sleep(2)

        # Get full image URL
        full_img = driver.find_element(By.CSS_SELECTOR, "img.n3VNCb")
        img_url = full_img.get_attribute("src")

        # Download the image
        image_name = topic.replace(" ", "_").lower() + ".jpg"
        image_path = os.path.join(save_dir, image_name)

        img_data = requests.get(img_url, timeout=10).content
        with open(image_path, "wb") as f:
            f.write(img_data)

        print(f"✅ Image downloaded: {image_path}")
        return image_path

    finally:
        driver.quit()


if __name__ == "__main__":
    topic = input("Enter topic: ")
    download_first_google_image(topic)
