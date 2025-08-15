import time
import json
import random
import tls_client
import undetected_chromedriver
from capmonster_python import CapmonsterClient, TurnstileTask

print("PlaceBot(autologin.py) by @raizouxyz")
print("Repository: https://github.com/raizouxyz/placebot\n")

config = json.load(open("./data/config.json", "r"))

with open("./data/google.txt", "r") as f:
    accounts = [line.strip().split(":") for line in f.readlines()]

proxies = []
with open("./data/proxies.txt", "r") as f:
    _proxies = f.read().splitlines()
    for _proxy in _proxies:
        proxy = {"http": _proxy, "https": _proxy}
        proxies.append(proxy)

client = CapmonsterClient(api_key=config["capmonster_apikey"])
session = tls_client.Session(client_identifier="chrome_124",random_tls_extension_order=True)

def get_headers(token=None):
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }

    if token:
        headers["Cookie"] = f"j={token}"

    return headers

for account in accounts:
    email = account[0]
    password = account[1]

    task_id = client.create_task(TurnstileTask(
        websiteURL="https://wplace.live",
        websiteKey="0x4AAAAAABpHqZ-6i7uL0nmG"
    ))
    while True:
        result = client.get_task_result(task_id)
        if "token" in result:
            turnstile_token = result["token"]
            break
        time.sleep(1)

    driver = undetected_chromedriver.Chrome()
    driver.options.proxy = undetected_chromedriver.selenium.webdriver.Proxy(random.choice(proxies))
    driver.get(f'https://backend.wplace.live/auth/google?token={turnstile_token}')
    driver.find_element(undetected_chromedriver.By.ID, "identifierId").send_keys(email)
    driver.find_element(undetected_chromedriver.By.ID, "identifierNext").click()
    while True:
        if driver.current_url.startswith("https://accounts.google.com/v3/signin/challenge/pwd"):
            break
        time.sleep(0.2)
    try:
        driver.implicitly_wait(4)
        driver.find_element(undetected_chromedriver.By.NAME, "Passwd").send_keys(password)
    except:
        continue
    driver.find_element(undetected_chromedriver.By.ID, "passwordNext").click()
    while True:
        if driver.current_url.startswith("https://wplace.live/"):
            break
        time.sleep(0.2)
    driver.get("https://backend.wplace.live/me")
    token = driver.get_cookie("j")["value"]
    print(token)
    tokens += token
    
    driver.quit()
    time.sleep(10)

with open("./data/tokens.txt", "w") as f:
    f.write("\n".join(tokens))
