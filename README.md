# [PlaceBot](https://discord.gg/romeda)
Botting tool for wplace.live
## Features
- Place on the map according to the image file (place.py)
- Monitor the map and revert repainted pixels (keep.py)
- Voiding (void.py)
- Automatically log in with your Google account email and password and obtain a token (autologin.py)
- Check if your account is active and not suspended (check.py)
- Convert image file to a color that can be used in wplace.live (convert.py)
## Note
### Coordinate specification
Communication when clicking a pixel on the map  
```https://backend.wplace.live/s0/pixel/chunk_x/chunk_y?x=start_x&y=start_y```
### Color Palette
Eraser = 0, #000000 = 1, #3c3c3c = 2, #787878 = 3, #d2d2d2 = 4, #ffffff = 5, #600018 = 6, #ed1c24 = 7, #ff7f27 = 8, #f6aa09 = 9,  
#f9dd3b = 10, #fffabc = 11, #0eb968 = 12, #13e67b = 13, #87ff5e = 14, #0c816e = 15, #10aea6 = 16, #13e1be = 17, #28509e = 18, #4093e4 = 19,  
#60f7f2 = 20, #6b50f6 = 21, #99b1fb = 22, #780c99 = 23, #aa38b9 = 24, #e09ff9 = 25, #cb007a = 26, #ec1f80 = 27, #f38da9 = 28, #684634 = 29,  
#95682a = 30, #f8b277 = 31
