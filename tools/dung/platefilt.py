"""Lọc biển số giả (chùm quả cà phê, mép bàn gỗ, lá, trời): biển xe VN nền trắng/xanh, chữ tối, độ tương phản cao."""
import cv2, numpy as np
def plate_like(img, x, y, w, h):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = int(max(0, x)), int(max(0, y)), int(min(W, x + w)), int(min(H, y + h))
    if x1 - x0 < 8 or y1 - y0 < 6: return False
    r = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
    S, Vsd, Hm = r[:, 1].mean(), r[:, 2].std(), float(np.median(r[:, 0]))
    return (S < 75 and Vsd >= 25) or (90 <= Hm <= 135 and Vsd >= 45)
