import argparse
import sys
from PIL import Image
import numpy as np

_have_sklearn = False
_have_scipy = False
_have_skimage = False
_have_colormath = False
try:
    from sklearn.neighbors import KDTree
    _have_sklearn = True
except Exception:
    _have_sklearn = False

try:
    from scipy.spatial import cKDTree as ScipyKDTree
    _have_scipy = True
except Exception:
    _have_scipy = False

try:
    from skimage.color import rgb2lab
    _have_skimage = True
except Exception:
    _have_skimage = False

try:
    from colormath.color_objects import sRGBColor, LabColor
    from colormath.color_conversions import convert_color
    from colormath.color_diff import delta_e_cie2000
    _have_colormath = True
except Exception:
    _have_colormath = False


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', required=True, help='入力画像ファイルパス')
    p.add_argument('--method', '-m', choices=['rgb', 'weighted', 'lab'], default='rgb')
    p.add_argument('--reduce_unique', action='store_true')
    return p.parse_args()


def load_palette(path):
    colors = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith('#') and len(s) == 1:
                continue
            if s.startswith('#'):
                s = s[1:]
            if len(s) == 3:
                s = ''.join([c*2 for c in s])
            if len(s) != 6:
                raise ValueError(f'パレットの色がHEX 6桁ではありません: {ln!r}')
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            colors.append((r, g, b))
    if not colors:
        raise ValueError('パレットが空です。')
    return np.array(colors, dtype=np.uint8)


def rgb_to_array(img):
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        return arr[:, :, :3], arr[:, :, 3]
    return arr, None


def build_nn_index(palette_arr, metric='euclidean'):
    palette_float = palette_arr.astype(float)
    if _have_sklearn:
        tree = KDTree(palette_float, leaf_size=40, metric=metric)
        def query(points):
            dist, idx = tree.query(points, return_distance=True)
            return idx if idx.ndim == 1 else idx[:,0]
        return query
    if _have_scipy:
        tree = ScipyKDTree(palette_float)
        def query(points):
            _, idx = tree.query(points)
            return idx
        return query
    def query(points):
        M = points.shape[0]
        N = palette_float.shape[0]
        idxs = np.empty(M, dtype=int)
        chunk = 100000
        for start in range(0, M, chunk):
            end = min(M, start+chunk)
            pts = points[start:end][:, None, :]  # (C,1,3)
            dif = pts - palette_float[None, :, :]  # (C,N,3)
            d2 = np.sum(dif*dif, axis=2)  # (C,N)
            idxs[start:end] = np.argmin(d2, axis=1)
        return idxs

def rgb_distance_map_method(method):
    if method == 'rgb':
        return lambda arr: arr.astype(float)
    if method == 'weighted':
        scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
        return lambda arr: arr.astype(float) * scale[None, None, :]
    if method == 'lab':
        if _have_skimage:
            def to_lab(arr):
                f = arr.astype('float32') / 255.0
                return lab
            return to_lab
        elif _have_colormath:
            def to_lab(arr):
                h, w, _ = arr.shape
                flat = arr.reshape(-1, 3)
                uniq, inv = np.unique(flat, axis=0, return_inverse=True)
                lab_list = []
                for (r,g,b) in uniq:
                    srgb = sRGBColor(r/255.0, g/255.0, b/255.0, is_upscaled=False)
                    lab = convert_color(srgb, LabColor)
                    lab_list.append([lab.lab_l, lab.lab_a, lab.lab_b])
                lab_arr = np.array(lab_list, dtype=float)[inv].reshape(h, w, 3)
                return lab_arr
            return to_lab
        else:
            print("警告: skimage または colormath が利用できないため、'lab' を計算できません。'weighted'で代替します。", file=sys.stderr)
            scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
            return lambda arr: arr.astype(float) * scale[None, None, :]
    raise ValueError('unknown method')

def main():
    print("PlaceBot(convert.py) by @raizouxyz")
    print("Repository: https://github.com/raizouxyz/placebot\n")
    
    args = parse_args()

    palette = load_palette("./palette.txt")
    print(f'読み込んだパレット: {palette.shape[0]} 色')

    img = Image.open(args.input)
    orig_mode = img.mode
    has_alpha = ('A' in orig_mode)
    pixels, alpha = rgb_to_array(img)
    H, W, _ = pixels.shape
    print(f'入力画像: {args.input} -> {W}x{H}, モード={orig_mode}')

    method = args.method
    to_space = rgb_distance_map_method(method)

    if method == 'lab':
        if _have_skimage:
            pal_f = palette.astype('float32') / 255.0
            pal_lab = rgb2lab(pal_f.reshape(1, -1, 3)).reshape(-1, 3)
        elif _have_colormath:
            pal_lab = []
            for (r,g,b) in palette:
                srgb = sRGBColor(r/255.0, g/255.0, b/255.0, is_upscaled=False)
                lab = convert_color(srgb, LabColor)
                pal_lab.append([lab.lab_l, lab.lab_a, lab.lab_b])
            pal_lab = np.array(pal_lab, dtype=float)
        else:
            pal_lab = (palette.astype(float) * np.array([2**0.5,2.0,3**0.5])[None,:])
    else:
        if method == 'rgb':
            pal_lab = palette.astype(float)
        else:
            scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
            pal_lab = palette.astype(float) * scale[None, :]

    palette_space = pal_lab.astype(float)

    if args.reduce_unique:
        flat = pixels.reshape(-1, 3)
        uniq_colors, inv = np.unique(flat, axis=0, return_inverse=True)
        print(f'ユニーク色数: {uniq_colors.shape[0]} (reduce_unique ON)')
        if method == 'lab' and ( _have_skimage or _have_colormath):
            uniq_img = uniq_colors.reshape(-1,1,3).astype(np.uint8)
            uniq_lab = to_space(uniq_img).reshape(-1,3)
            query_points = uniq_lab
        else:
            query_points = (uniq_colors.astype(float) * (np.array([1,1,1]) if method=='rgb' else np.array([2**0.5,2.0,3**0.5]))[None,:])
    else:
        if method == 'lab' and (_have_skimage or _have_colormath):
            img_space = to_space(pixels)
        else:
            img_space = to_space(pixels)
        flat = img_space.reshape(-1,3)
        query_points = flat

    if _have_sklearn:
        tree = KDTree(palette_space)
        M = query_points.shape[0]
        batch = 200000
        idxs = np.empty(M, dtype=int)
        for s in range(0, M, batch):
            e = min(M, s+batch)
            dist, idc = tree.query(query_points[s:e], k=1)
            idxs[s:e] = idc[:,0]
    elif _have_scipy:
        tree = ScipyKDTree(palette_space)
        idxs = tree.query(query_points)[1]
    else:
        M = query_points.shape[0]
        N = palette_space.shape[0]
        idxs = np.empty(M, dtype=int)
        chunk = 100000
        for s in range(0, M, chunk):
            e = min(M, s+chunk)
            pts = query_points[s:e][:,None,:]
            dif = pts - palette_space[None,:,:]
            d2 = np.sum(dif*dif, axis=2)
            idxs[s:e] = np.argmin(d2, axis=1)

    if args.reduce_unique:
        mapped_palette_indices = idxs
        flat_pixels = pixels.reshape(-1,3)
        mapped_idx_for_flat = mapped_palette_indices[inv]
    else:
        mapped_idx_for_flat = idxs

    out_flat = palette[mapped_idx_for_flat]
    out_img_arr = out_flat.reshape(H, W, 3).astype(np.uint8)

    if alpha is not None:
        out_rgba = np.dstack([out_img_arr, alpha])
        out_pil = Image.fromarray(out_rgba, 'RGBA')
    else:
        out_pil = Image.fromarray(out_img_arr, 'RGB')

    _output = args.input.split(".")
    output = _output[0] + "_converted." + _output[1]

    out_pil.save(output)
    print(f'変換完了: {output}')

if __name__ == '__main__':
    main()
