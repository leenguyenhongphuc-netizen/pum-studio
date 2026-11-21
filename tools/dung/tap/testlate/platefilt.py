"""Lọc biển số giả (chùm quả cà phê, cầu thang chạm khắc, mũ, đệm ngồi, mép bàn): biển xe VN nền trắng sáng
(hoặc ánh xanh khi trong bóng râm) hay nền vàng (taxi, xe kinh doanh), chữ tối, tương phản cao."""
import cv2, numpy as np
def plate_like(img, x, y, w, h):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = int(max(0, x)), int(max(0, y)), int(min(W, x + w)), int(min(H, y + h))
    if x1 - x0 < 8 or y1 - y0 < 6: return False
    r = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
    Hm, Vsd = float(np.median(r[:, 0])), r[:, 2].std()
    bright = ((r[:, 2] > 150) & (r[:, 1] < 70)).mean()
    orange = ((r[:, 0] >= 8) & (r[:, 0] <= 34) & (r[:, 1] > 90) & (r[:, 2] > 130)).mean()  # biển vàng/cam (taxi)
    red = (((r[:, 0] < 8) | (r[:, 0] > 165)) & (r[:, 1] > 90)).mean()
    green = ((r[:, 0] > 35) & (r[:, 0] < 90) & (r[:, 1] > 60)).mean()
    dark = (r[:, 2] < 90).mean()
    return (bright >= 0.45 or (90 <= Hm <= 135 and (Vsd >= 45 or bright >= 0.3))
            or (orange >= 0.3 and red <= 0.2 and green <= 0.1 and 0.05 <= dark <= 0.6))
