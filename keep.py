from io import BytesIO
import json
import random
import time
import requests
import tls_client
from PIL import Image
from capmonster_python import CapmonsterClient, TurnstileTask

##################################################
image_path = "./images/romeda.png"
skip_color = "#000000"
chunk_x = 0
chunk_y = 0
start_x = 0
start_y = 0
##################################################

print("PlaceBot(keep.py) by @raizouxyz")
print("Repository: https://github.com/raizouxyz/placebot\n")

config = json.load(open("./data/config.json", "r"))

base_img = Image.open(image_path)
base_rgb_img = base_img.convert("RGB")

proxies = []
with open("./data/proxies.txt", "r") as f:
    _proxies = f.read().splitlines()
    for _proxy in _proxies:
        proxy = {"http": _proxy, "https": _proxy}
        proxies.append(proxy)

with open("./data/tokens.txt", "r") as f:
    tokens = f.read().splitlines()

session = tls_client.Session(client_identifier="chrome_124",random_tls_extension_order=True)
client = CapmonsterClient(api_key=config["capmonster_apikey"])

def get_headers(token=None):
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }

    if token:
        headers["Cookie"] = f"j={token}"

    return headers

nextaccount = False
while True:
    try:
        skip_x = 0
        skip_y = 0
        response = requests.get(f"https://backend.wplace.live/files/s0/tiles/{chunk_x}/{chunk_y}.png")
        img = Image.open(BytesIO(response.content))
        rgb_img = img.convert("RGB")
        for token in tokens:
            response = session.get("https://backend.wplace.live/me", headers=get_headers(token), proxies=random.choice(proxies))
            if response.status_code == 200:
                droplets = response.json()["droplets"]
                charge_seconds = response.json()["charges"]["cooldownMs"] / 1000
                charge = int(response.json()["charges"]["count"])
                charge_max = response.json()["charges"]["max"]
                request_data = {"colors":[],"coords":[],"t":""}
                for x in range(base_rgb_img.size[0]):
                    if x+start_x < skip_x:
                        continue
                    for y in range(base_rgb_img.size[1]):
                        if x+start_x < skip_x and y+start_y < skip_y:
                            continue
                        base_pixel = base_rgb_img.getpixel((x, y))
                        pixel = rgb_img.getpixel((x + start_x, y + start_y))
                        base_color_code = "#"+''.join(f"{c:02x}" for c in base_pixel)
                        color_code = "#"+''.join(f"{c:02x}" for c in pixel)
                        if base_color_code == skip_color:
                            continue

                        if color_code != base_color_code:
                            request_data["colors"].append(5)
                            request_data["coords"].append(start_x+x)
                            request_data["coords"].append(start_y+y)
                            charge -= 1
                        if charge < 1:
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

                            if len(request_data["colors"]) > 0:
                                response = session.post(f"https://backend.wplace.live/s0/pixel/{chunk_x}/{chunk_y}", headers=get_headers(token), proxies=random.choice(proxies),  data=json.dumps(request_data))
                                print(response.status_code, response.text)
                                if response.status_code == 200:
                                    painted = response.json()['painted']
                                    response = session.get("https://backend.wplace.live/me", headers=get_headers(token), proxies=random.choice(proxies))
                                    if response.status_code == 200:
                                        droplets = response.json()["droplets"]
                                        charge = int(response.json()["charges"]["count"])
                                    request_data = {"colors":[],"coords":[],"t":""}
                                    print(f"[Placed] 配置数:{painted} 最終座標:({start_x+x},{start_y+y}) 色:{0} 残り配置可能数:{charge}")
                                    skip_x = x + start_x
                                    skip_y = y + start_y
                                else:
                                    tokens.remove(token)

                                if droplets >= 500 and charge < (charge_max - 32):
                                    response = session.post("https://backend.wplace.live/purchase", headers=get_headers(token), proxies=random.choice(proxies), data=json.dumps({"product":{"id":80,"amount":1}}))
                                    print("[Purchase] 配置可能数を購入(+30)")
                                    droplets -= 500
                                    charge += 30
                                    continue

                            nextaccount = True
                            print(f"[Charge] {charge_seconds}秒待機")
                            time.sleep(charge_seconds)
                            response = session.get("https://backend.wplace.live/me", headers=get_headers(token))
                            charge = int(response.json()["charges"]["count"])
                        if nextaccount:
                            break
                    if nextaccount:
                        break
                nextaccount = False
            else:
                tokens.remove(token)
    except:
        pass
