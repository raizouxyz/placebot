import json
import random
import time
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
skip_x = 0
skip_y = 0
##################################################

print("PlaceBot(place.py) by @raizouxyz")
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

palette = {"#000000": 1,"#3c3c3c": 2,"#787878": 3,"#d2d2d2": 4,"#ffffff": 5,"#600018": 6,"#ed1c24": 7,"#ff7f27": 8,"#f6aa09": 9,"#f9dd3b": 10,"#fffabc": 11,"#0eb968": 12,"#13e67b": 13,"#87ff5e": 14,"#0c816e": 15,"#10aea6": 16,"#13e1be": 17,"#28509e": 18,"#4093e4": 19,"#60f7f2": 20,"#6b50f6": 21,"#99b1fb": 22,"#780c99": 23,"#aa38b9": 24,"#e09ff9": 25,"#cb007a": 26,"#ec1f80": 27,"#f38da9": 28,"#684634": 29,"#95682a": 30,"#f8b277": 31}

img = Image.open(image_path)
rgb_img = img.convert("RGB")

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
    for token in tokens:
        response = session.get("https://backend.wplace.live/me", headers=get_headers(token), proxies=random.choice(proxies))
        if response.status_code == 200:
            droplets = response.json()["droplets"]
            charge_seconds = response.json()["charges"]["cooldownMs"] / 1000
            charge = int(response.json()["charges"]["count"])
            charge_max = response.json()["charges"]["max"]
            request_data = {"colors":[],"coords":[],"t":""}

            for x in range(rgb_img.size[0]):
                if x+start_x < skip_x:
                    continue
                for y in range(rgb_img.size[1]):
                    if x+start_x == skip_x and y+start_y < skip_y:
                        continue

                    if charge >= 1:
                        pixel = rgb_img.getpixel((x, y))
                        color_code = "#"+''.join(f"{c:02x}" for c in pixel)
                        if color_code == skip_color or color_code not in palette:
                            continue

                        color = palette.get(color_code)

                        request_data["colors"].append(color)
                        request_data["coords"].append(start_x+x)
                        request_data["coords"].append(start_y+y)
                        charge -= 1
                    if (x == rgb_img.size[0] - 1 and y == rgb_img.size[1] - 1) or (charge < 1):
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
                            response = session.post(f"https://backend.wplace.live/s0/pixel/{chunk_x}/{chunk_y}", headers=get_headers(token), proxies=random.choice(proxies), data=json.dumps(request_data))
                            print(response.status_code, response.text)
                            if response.status_code == 200:
                                painted = response.json()['painted']
                                response = session.get("https://backend.wplace.live/me", headers=get_headers(token), proxies=random.choice(proxies))
                                if response.status_code == 200:
                                    droplets = response.json()["droplets"]
                                    charge = int(response.json()["charges"]["count"])
                                request_data = {"colors":[],"coords":[],"t":""}
                                print(f"[Placed] 配置数:{painted} 最終座標:({start_x+x},{start_y+y}) 色:{color} 残り配置可能数:{charge}")
                                skip_x = x + start_x
                                skip_y = y + start_y
                            else:
                                print(token)

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
            print(response.status_code, response.text)
