"""
convert.py

説明:
  画像ファイルの各ピクセルを、与えたカラーパレット内の「最も近い色」に置き換えます。
  距離の測り方は --method で選べます: 'rgb' (単純RGB), 'weighted' (NTSC風重み付きRGB), 'lab' (CIE Lab + ΔE(ユークリッド) / ΔE2000 if colormath available)

使い方の例:
  py convert.py -i images/kiku.png

パレットファイル (palette.txt) のフォーマット:
  1行に1色、HEX表記 (例: #RRGGBB または RRGGBB) を並べるだけ。
"""

import argparse
import sys
from PIL import Image
import numpy as np

# try to import fast nearest neighbor implementations / color libs
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
    # colormath gives ΔE2000; used only for more accurate Lab ΔE if available
    from colormath.color_objects import sRGBColor, LabColor
    from colormath.color_conversions import convert_color
    from colormath.color_diff import delta_e_cie2000
    _have_colormath = True
except Exception:
    _have_colormath = False


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', required=True, help='入力画像ファイルパス')
    p.add_argument('--method', '-m', choices=['rgb', 'weighted', 'lab'], default='rgb',
                   help='距離の取り方: rgb / weighted / lab (default: weighted). labはcolormathかskimageがあると良い')
    p.add_argument('--reduce_unique', action='store_true',
                   help='画素のユニーク色だけをマッチングして速度向上（ほとんどの場合有効）')
    return p.parse_args()


def load_palette(path):
    """パレットファイルを読み、RGBタプルのリストを返す"""
    colors = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith('#') and len(s) == 1:
                continue
            # remove leading '#'
            if s.startswith('#'):
                s = s[1:]
            # support short hex? (abc -> aabbcc)
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
    """PIL画像 -> (H,W,3) uint8 ndarray"""
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        # discard alpha for matching; keep for output later if present
        return arr[:, :, :3], arr[:, :, 3]
    return arr, None


def build_nn_index(palette_arr, metric='euclidean'):
    """palette_arr: (N,3) float array -> returns a function nearest(query_points) -> indices"""
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
    # fallback: brute force (slower)
    def query(points):
        # points: (M,3)
        # compute squared distances to palette (N,3) broadcasting -> (M,N)
        # careful with memory: do in chunks if needed
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
    # unreachable


def rgb_distance_map_method(method):
    if method == 'rgb':
        # raw RGB
        return lambda arr: arr.astype(float)
    if method == 'weighted':
        # NTSC-like weights: sqrt(2 R^2 + 4 G^2 + 3 B^2) -> we encode by scaling channels
        # scale channels so Euclidean on scaled RGB approx weighted distance
        # i.e., distance^2 = 2 dR^2 + 4 dG^2 + 3 dB^2 = (sqrt2 dR)^2 + (2 dG)^2 + (sqrt3 dB)^2
        scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
        return lambda arr: arr.astype(float) * scale[None, None, :]
    if method == 'lab':
        # Lab conversion: prefer skimage (vectorized). If not, try colormath per color.
        if _have_skimage:
            def to_lab(arr):
                # arr: HxWx3 uint8 [0,255]
                # skimage.rgb2lab expects float in [0,1]
                f = arr.astype('float32') / 255.0
                lab = rgb2lab(f)  # returns L,a,b floats
                return lab
            return to_lab
        elif _have_colormath:
            # convert per unique color using colormath (slower)
            def to_lab(arr):
                # arr: HxWx3 uint8
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
            # fallback: warn and use weighted RGB
            print("警告: skimage または colormath が利用できないため、'lab' を計算できません。'weighted'で代替します。", file=sys.stderr)
            scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
            return lambda arr: arr.astype(float) * scale[None, None, :]
    raise ValueError('unknown method')


def main():
    args = parse_args()

    # load palette
    palette = load_palette("./palette.txt")  # (N,3) uint8
    print(f'読み込んだパレット: {palette.shape[0]} 色')

    # open image
    img = Image.open(args.input)
    orig_mode = img.mode
    has_alpha = ('A' in orig_mode)
    pixels, alpha = rgb_to_array(img)  # pixels: HxWx3 uint8
    H, W, _ = pixels.shape
    print(f'入力画像: {args.input} -> {W}x{H}, モード={orig_mode}')

    method = args.method
    to_space = rgb_distance_map_method(method)

    # convert palette to the chosen space
    if method == 'lab':
        # palette -> Lab
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
            # fallback: use weighted RGB mapping (already handled in to_space)
            pal_lab = (palette.astype(float) * np.array([2**0.5,2.0,3**0.5])[None,:])
    else:
        # rgb or weighted -> palette scaled similarly
        if method == 'rgb':
            pal_lab = palette.astype(float)
        else:
            scale = np.array([2**0.5, 2.0, 3**0.5], dtype=float)
            pal_lab = palette.astype(float) * scale[None, :]

    # Build NN index on palette in target space
    # Flatten palette to (N,3)
    palette_space = pal_lab.astype(float)

    # prepare image points
    if args.reduce_unique:
        flat = pixels.reshape(-1, 3)
        uniq_colors, inv = np.unique(flat, axis=0, return_inverse=True)
        print(f'ユニーク色数: {uniq_colors.shape[0]} (reduce_unique ON)')
        # convert uniq_colors to target space
        # we need a function that accepts (M,3) and returns (M,3) in palette space scale
        if method == 'lab' and ( _have_skimage or _have_colormath):
            # reuse to_space which expects HxWx3; craft small HxW
            uniq_img = uniq_colors.reshape(-1,1,3).astype(np.uint8)
            uniq_lab = to_space(uniq_img).reshape(-1,3)
            query_points = uniq_lab
        else:
            # rgb/weighted or fallback
            query_points = (uniq_colors.astype(float) * (np.array([1,1,1]) if method=='rgb' else np.array([2**0.5,2.0,3**0.5]))[None,:])
    else:
        # use all pixels (may be heavy). Convert full image to target space
        if method == 'lab' and (_have_skimage or _have_colormath):
            img_space = to_space(pixels)
        else:
            # rgb/weighted
            img_space = to_space(pixels)
        flat = img_space.reshape(-1,3)
        query_points = flat

    # choose nearest neighbor backend
    if _have_sklearn:
        tree = KDTree(palette_space)
        # query in batches to control memory
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
        # brute force
        # compute distances chunked
        M = query_points.shape[0]
        N = palette_space.shape[0]
        idxs = np.empty(M, dtype=int)
        chunk = 100000
        for s in range(0, M, chunk):
            e = min(M, s+chunk)
            pts = query_points[s:e][:,None,:]  # (C,1,3)
            dif = pts - palette_space[None,:,:]
            d2 = np.sum(dif*dif, axis=2)
            idxs[s:e] = np.argmin(d2, axis=1)

    # if we reduced to uniques, map back
    if args.reduce_unique:
        mapped_palette_indices = idxs  # length = uniq_colors
        # build a mapping for every pixel
        flat_pixels = pixels.reshape(-1,3)
        mapped_idx_for_flat = mapped_palette_indices[inv]
    else:
        mapped_idx_for_flat = idxs

    # create output image data
    out_flat = palette[mapped_idx_for_flat]  # (H*W, 3)
    out_img_arr = out_flat.reshape(H, W, 3).astype(np.uint8)

    # restore alpha if existed
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
