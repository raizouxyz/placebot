import json
import random
import time
import tls_client
from capmonster_python import CapmonsterClient, TurnstileTask

##################################################
suspend_check = True
##################################################

print("PlaceBot(check.py) by @raizouxyz")
print("Repository: https://github.com/raizouxyz/placebot\n")

config = json.load(open("./data/config.json", "r"))

proxies = []
with open("./data/proxies.txt", "r") as f:
    _proxies = f.read().splitlines()
    for _proxy in _proxies:
        proxy = {"http": _proxy, "https": _proxy}
        proxies.append(proxy)

with open("./data/tokens.txt", "r") as f:
    tokens = f.read().splitlines()

session = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
client = CapmonsterClient(api_key=config["capmonster_apikey"])

def get_headers(token=None):
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }

    if token:
        headers["Cookie"] = f"j={token}"

    return headers

charges_total = 0
for token in tokens:
    response = session.get("https://backend.wplace.live/me", headers=get_headers(token), proxies=random.choice(proxies))
    print(response.status_code, response.text)
    user_name = response.json()['name']
    user_id = response.json()['id']
    charge = int(response.json()["charges"]["count"])
    charge_max = response.json()["charges"]["max"]
    droplets = response.json()["droplets"]
    purchasable_charges = int(droplets/500)*30
    if response.status_code == 200:
        if suspend_check:
            request_data = {"colors":[0],"coords":[random.randint(0, 1000), random.randint(0, 1000)],"t":""}
            task_id = client.create_task(TurnstileTask(
                websiteURL="https://wplace.live",
                websiteKey="0x4AAAAAABpqJe8FO0N84q0F"
            ))
            while True:
                result = client.get_task_result(task_id)
                if "token" in result:
                    request_data["t"] = result["token"]
                    break
                time.sleep(1)

            response = session.post(f"https://backend.wplace.live/s0/pixel/0/0", headers=get_headers(token), proxies=random.choice(proxies),  data=json.dumps(request_data))
            if response.status_code != 200:
                tokens.remove(token)
                continue
        print(f"[Information] {user_name}({user_id}) 配置可能:{charge}/{charge_max}(購入可能:{purchasable_charges}) Droplets:{droplets}")
        charges_total += charge + purchasable_charges
    else:
        tokens.remove(token)

with open("./data/tokens.txt", "w") as f:
    f.write("\n".join(tokens))
print(f"合計配置可能数:{charges_total} アカウント数:{len(tokens)}")
