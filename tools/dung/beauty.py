"""Làm đẹp theo video mẫu của Pum: màu (filter), da, mặt (mắt, hàm, cằm, má) và dáng (eo, tay).
Chỉ áp cho mặt và người của Pum (mặt lớn nhất khớp vector mặt Pum). Mức chỉnh đọc từ preset JSON.

Dùng như module:  B = Beauty(json.load(open("beauty_pum.json"))); out = B.apply(frame_bgr)
Hoặc lệnh:       python3 -I beauty.py preset.json in.mp4 out.mp4 [--ss 3 --to 8] [--side]
                 python3 -I beauty.py measure ref1.mp4 [ref2.mp4 ...]   (đo video mẫu → số liệu để chỉnh preset)
Mô hình (tải một lần vào ~/models hoặc /home/claude/models):
  face_landmarker.task, pose_landmarker_full.task (storage.googleapis.com/mediapipe-models/...)
"""
import json, os, sys, subprocess, pathlib
import numpy as np, cv2

MD = pathlib.Path(os.environ.get("PUM_MODELS", "/home/claude/models"))

# chỉ số điểm mốc MediaPipe Face Mesh
LIP_OUT = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
LIP_IN = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191]
JAW_L = [172, 136, 150, 149, 176]; JAW_R = [397, 365, 379, 378, 400]
CHEEK_L, CHEEK_R = [234, 93, 132], [454, 323, 361]
EYE_L, EYE_R = [33, 133, 159, 145], [362, 263, 386, 374]
CHIN, NOSE, LIP_LOW = 152, 1, 17
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
HOLES = [[33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],            # mắt trái
         [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398],     # mắt phải
         [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185],  # môi
         [70, 63, 105, 66, 107, 55, 65, 52, 53, 46], [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]]  # mày

DEFAULT = {
    "color": {"exposure": 0.0, "contrast": 1.0, "saturation": 1.0, "warmth": 0.0, "tint": 0.0, "glow": 0.0, "lift": 0.0},
    "skin": {"smooth": 0.0, "brighten": 0.0, "blush": 0.0, "rosy": 0.0, "lips": 0.0, "lip_lab": [128, 163, 144], "gloss": 0.0},
    "face": {"eyes": 0.0, "jaw": 0.0, "chin": 0.0, "cheek": 0.0},
    "body": {"waist": 0.0, "arms": 0.0},
    "smooth_landmarks": 0.6,
}


def merge(a, b):
    o = json.loads(json.dumps(a))
    for k, v in (b or {}).items():
        o[k] = merge(o[k], v) if isinstance(v, dict) and isinstance(o.get(k), dict) else v
    return o


class Beauty:
    def __init__(self, preset=None, video=True):
        import mediapipe as mp
        from mediapipe.tasks.python import vision, BaseOptions
        self.mp = mp; self.P = merge(DEFAULT, preset or {})
        mode = vision.RunningMode.VIDEO if video else vision.RunningMode.IMAGE
        self.fl = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MD / "face_landmarker.task")), running_mode=mode, num_faces=3,
            min_face_detection_confidence=0.5, min_tracking_confidence=0.5))
        self.pose = None
        if self.P["body"]["waist"] or self.P["body"]["arms"]:
            self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MD / "pose_landmarker_full.task")), running_mode=mode, num_poses=2))
        self.video = video; self.ts = 0; self.prev = None; self.prevp = None
        self.ref = None
        rp = MD / "pum_ref.npy"
        if rp.exists():
            self.ref = np.load(rp)
            self.rec = cv2.FaceRecognizerSF.create(str(MD / "face_recognition_sface_2021dec.onnx"), "")
            self.det = cv2.FaceDetectorYN.create(str(MD / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.6, 0.3, 50)

    # ---------- nhận diện ----------
    def _landmarks(self, img):
        h, w = img.shape[:2]; sm = img if max(h, w) <= 1000 else cv2.resize(img, (w * 960 // max(h, w), h * 960 // max(h, w)), interpolation=cv2.INTER_AREA)
        mi = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(sm, cv2.COLOR_BGR2RGB))
        if self.video:
            self.ts += 33; r = self.fl.detect_for_video(mi, self.ts)
        else:
            r = self.fl.detect(mi)
        faces = [np.array([[l.x * w, l.y * h] for l in f]) for f in r.face_landmarks]
        self.nf = getattr(self, "nf", 0) + 1
        lm = None
        if faces:
            faces.sort(key=lambda f: -(np.ptp(f[:, 0]) * np.ptp(f[:, 1])))
            lm = faces[0]; fw = np.ptp(lm[:, 0])
            tracking = self.prev is not None and np.abs(self.prev.mean(0) - lm.mean(0)).max() < 0.25 * fw
            # chỉ kiểm danh tính khi mới bắt được mặt hoặc 30 khung một lần: kiểm từng khung làm hiệu ứng bật tắt liên tục
            if self.ref is not None and (not tracking or self.nf % 30 == 0):
                self.ok = self._is_pum(img, lm)
            elif not tracking: self.ok = True
            if not getattr(self, "ok", True): lm = None
        if lm is None:
            self.lost = getattr(self, "lost", 0) + 1
            if self.prev is not None and self.lost <= 6:  # giữ điểm mốc cũ vài khung, tắt dần cho mượt
                self.gain = max(0.0, getattr(self, "gain", 0) - 0.18); return self.prev if self.gain > 0 else None
            self.prev = None; self.gain = 0.0; return None
        self.lost = 0
        if self.prev is not None and self.prev.shape == lm.shape:
            # làm mượt theo từng điểm: điểm đứng yên (rung do máy nhận) được làm mượt mạnh, điểm đang chuyển động (miệng khi nói) giữ nguyên để không trễ khẩu hình
            fw = np.ptp(lm[:, 0]); d = np.linalg.norm(lm - self.prev, axis=1) / (fw + 1e-6)
            al = np.clip(self.P["smooth_landmarks"] * (1 - d / 0.008), 0, self.P["smooth_landmarks"])[:, None]
            lm = al * self.prev + (1 - al) * lm
        self.gain = min(1.0, getattr(self, "gain", 0) + 0.18)
        self.prev = lm; return lm

    def _is_pum(self, img, lm):
        fw = np.ptp(lm[:, 0])
        if fw < 40: return False
        h, w = img.shape[:2]; self.det.setInputSize((w, h)); _, f = self.det.detect(img)
        if f is None: return True  # yunet trượt khi nghiêng mặt: tin mặt lớn nhất
        c = lm.mean(0); best = min(f, key=lambda r: np.hypot(r[0] + r[2] / 2 - c[0], r[1] + r[3] / 2 - c[1]))
        e = self.rec.feature(self.rec.alignCrop(img, best)).flatten(); e /= np.linalg.norm(e) + 1e-9
        return float((self.ref @ e).max()) >= 0.28

    # ---------- biến dạng cục bộ ----------
    @staticmethod
    def _shift(mx, my, c, d, R):
        """dịch vùng tròn tâm c bán kính R một đoạn d (điểm ảnh), giảm dần ra mép"""
        dx = mx - c[0]; dy = my - c[1]; r2 = (dx * dx + dy * dy) / (R * R)
        k = np.clip(1 - r2, 0, 1) ** 2
        return -d[0] * k, -d[1] * k

    @staticmethod
    def _bulge(mx, my, c, R, s):
        """phóng to vùng tròn (mắt) hệ số s (0.1 = to hơn ~10% ở tâm)"""
        dx = mx - c[0]; dy = my - c[1]; r = np.sqrt(dx * dx + dy * dy) / R
        k = np.where(r < 1, 1 - s * (1 - r * r), 1.0)
        return dx * (k - 1), dy * (k - 1)

    def _face_field(self, lm, mx, my, F):
        fw = np.linalg.norm(lm[234] - lm[454]); ctr = lm[NOSE]
        ux, uy = np.zeros_like(mx), np.zeros_like(my)
        e = F["eyes"]
        if e:
            for idx in (EYE_L, EYE_R):
                c = lm[idx].mean(0); R = np.linalg.norm(lm[idx[0]] - lm[idx[1]]) * 1.05
                a, b = self._bulge(mx, my, c, R, e); ux += a; uy += b
        j = F["jaw"]
        if j:
            for idx in (JAW_L, JAW_R):
                for i in idx:
                    p = lm[i]; v = ctr - p; v = v / (np.linalg.norm(v) + 1e-6)
                    a, b = self._shift(mx, my, p, v * j * fw, fw * 0.22); ux += a / len(idx) * 2.2; uy += b / len(idx) * 2.2
        ch = F["cheek"]
        if ch:
            for idx in (CHEEK_L, CHEEK_R):
                for i in idx:
                    p = lm[i]; v = np.array([ctr[0] - p[0], 0.0]); v = v / (np.linalg.norm(v) + 1e-6)
                    a, b = self._shift(mx, my, p, v * ch * fw, fw * 0.2); ux += a / len(idx) * 1.6; uy += b / len(idx) * 1.6
        c = F["chin"]
        if c:
            p = lm[CHIN]; v = lm[LIP_LOW] - p; L = np.linalg.norm(v); v = v / (L + 1e-6)
            a, b = self._shift(mx, my, p, v * c * L, fw * 0.28); ux += a; uy += b
        return ux, uy

    def _body_field(self, img, mx, my, B):
        h, w = img.shape[:2]; sm = cv2.resize(img, (w * 640 // max(h, w), h * 640 // max(h, w)), interpolation=cv2.INTER_AREA)
        mi = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(sm, cv2.COLOR_BGR2RGB))
        r = self.pose.detect_for_video(mi, self.ts) if self.video else self.pose.detect(mi)
        ux, uy = np.zeros_like(mx), np.zeros_like(my)
        if not r.pose_landmarks: return ux, uy
        ps = [np.array([[l.x * w, l.y * h, l.visibility] for l in p]) for p in r.pose_landmarks]
        p = max(ps, key=lambda q: abs(q[11, 0] - q[12, 0]))  # người gần máy nhất (vai rộng nhất)
        pp = getattr(self, "prevp", None)
        if pp is not None and np.abs(pp[[11, 12], :2] - p[[11, 12], :2]).max() < 0.1 * w:
            p = p.copy(); p[:, :2] = 0.75 * pp[:, :2] + 0.25 * p[:, :2]  # dáng: làm mượt mạnh, tránh eo/tay rung
        self.prevp = p
        sw = abs(p[11, 0] - p[12, 0])
        if sw < 0.05 * w or min(p[11, 2], p[12, 2]) < 0.5: return ux, uy
        hips = min(p[23, 2], p[24, 2]) > 0.5
        cx = (p[11, 0] + p[12, 0] + p[23, 0] + p[24, 0]) / 4 if hips else (p[11, 0] + p[12, 0]) / 2
        if B["waist"]:
            for s_, hp in ((11, 23), (12, 24)):
                if hips:
                    wp = p[s_, :2] * 0.4 + p[hp, :2] * 0.6  # eo: 60% từ vai xuống hông
                else:  # selfie nửa người: ước lượng eo dưới vai ~1 bề ngang vai, hơi thu vào trong
                    wp = np.array([p[s_, 0] + (cx - p[s_, 0]) * 0.12, p[s_, 1] + sw * 1.0])
                    if wp[1] > h * 0.98: continue
                v = np.array([np.sign(cx - wp[0]), 0.0])
                a, b = self._shift(mx, my, wp, v * B["waist"] * sw, sw * 0.45); ux += a; uy += b
        if B["arms"]:
            for s, e in ((11, 13), (12, 14)):
                if min(p[s, 2], p[e, 2]) < 0.5: continue
                mp_ = (p[s, :2] + p[e, :2]) / 2; v = np.array([np.sign(cx - mp_[0]), 0.0])
                a, b = self._shift(mx, my, mp_, v * B["arms"] * sw, sw * 0.3); ux += a; uy += b
        return ux, uy

    # ---------- da ----------
    def _skin_mask(self, lm, shape):
        m = np.zeros(shape[:2], np.uint8)
        cv2.fillPoly(m, [lm[FACE_OVAL].astype(np.int32)], 255)
        for hole in HOLES: cv2.fillPoly(m, [lm[hole].astype(np.int32)], 0)
        fw = np.linalg.norm(lm[234] - lm[454]); e = max(3, int(fw * 0.07))
        m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (e, e)))
        k = int(fw * 0.12) | 1
        return cv2.GaussianBlur(m, (k, k), 0).astype(np.float32) / 255.0

    def _skin(self, img, lm, S):
        fw = np.linalg.norm(lm[234] - lm[454])
        x0, y0 = np.maximum(lm.min(0) - fw * 0.15, 0).astype(int); x1, y1 = np.minimum(lm.max(0) + fw * 0.15, [img.shape[1], img.shape[0]]).astype(int)
        roi = img[y0:y1, x0:x1].astype(np.float32); m = self._skin_mask(lm - [x0, y0], roi.shape)[..., None]
        out = roi.copy()
        if S["smooth"]:
            d = max(5, int(fw * 0.03) | 1)
            sm = cv2.bilateralFilter(roi, d, 40, d).astype(np.float32)
            hi = roi - cv2.GaussianBlur(roi, (0, 0), fw * 0.01 + 0.5)  # giữ lại chút kết cấu da
            sm = sm + hi * 0.35
            out = out * (1 - m * S["smooth"]) + sm * m * S["smooth"]
        if S["brighten"]:
            lab = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
            lab[..., 0] = lab[..., 0] + m[..., 0] * S["brighten"] * (255 - lab[..., 0]) * 0.35
            out = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        if S.get("rosy"):  # da hồng nhẹ: đẩy kênh a (đỏ-hồng) của da lên, không làm trắng
            lab = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
            lab[..., 1] += m[..., 0] * S["rosy"] * 10; lab[..., 2] -= m[..., 0] * S["rosy"] * 3
            out = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        if S["blush"]:
            bm = np.zeros(roi.shape[:2], np.float32)
            for i, j in ((50, 205), (280, 425)):
                c = ((lm[i] + lm[j]) / 2 - [x0, y0]).astype(int)
                cv2.ellipse(bm, tuple(int(v) for v in c), (int(fw * 0.13), int(fw * 0.09)), 0, 0, 360, 1.0, -1)
            bm = cv2.GaussianBlur(bm, (0, 0), fw * 0.06)[..., None] * m
            pink = np.array([150, 120, 240], np.float32)  # BGR hồng phấn
            out = out * (1 - bm * S["blush"]) + (out * 0.55 + pink * 0.45) * bm * S["blush"]
        if S.get("lips"):  # son: kéo màu môi về màu môi trong video mẫu (Lab a,b), giữ độ sáng và vân môi
            lmr = lm - [x0, y0]; mm = np.zeros(roi.shape[:2], np.uint8)
            cv2.fillPoly(mm, [lmr[LIP_OUT].astype(np.int32)], 255); cv2.fillPoly(mm, [lmr[LIP_IN].astype(np.int32)], 0)
            k = max(3, int(fw * 0.012) | 1); mm = cv2.GaussianBlur(mm, (k, k), 0).astype(np.float32)[..., None] / 255.0
            lab = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
            t = np.array(S["lip_lab"], np.float32); a = S["lips"] * mm[..., 0]
            lab[..., 1] = lab[..., 1] * (1 - a) + t[1] * a; lab[..., 2] = lab[..., 2] * (1 - a) + t[2] * a
            if S.get("gloss"):  # bóng nhẹ ở phần sáng của môi
                L = lab[..., 0]; hi = np.clip((L - np.percentile(L[mm[..., 0] > 0.5], 70) if (mm > 0.5).any() else L * 0) / 40, 0, 1)
                lab[..., 0] = L + hi * mm[..., 0] * S["gloss"] * 25
            out = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        img[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)

    # ---------- màu toàn khung ----------
    def _lut(self, C):
        key = json.dumps(C, sort_keys=True)
        if getattr(self, "_lk", None) == key: return self._lt
        x = np.arange(256, dtype=np.float32) / 255.0; luts = []
        for ch in range(3):  # B, G, R
            f = x * (2 ** C["exposure"]); f = C["lift"] + f * (1 - C["lift"]); f = (f - 0.5) * C["contrast"] + 0.5
            if ch == 2: f = f + C["warmth"] * 0.06 + C["tint"] * 0.03
            if ch == 0: f = f - (C["warmth"] * 0.05 - C["tint"] * 0.02)
            if ch == 1: f = f - C["tint"] * 0.03
            luts.append(np.clip(f * 255, 0, 255).astype(np.uint8))
        self._lk = key; self._lt = np.stack(luts, 1)[:, None, :].reshape(256, 1, 3); return self._lt

    def _color(self, img, C):
        if not any(v for k, v in C.items() if k not in ("contrast", "saturation")) and C["contrast"] == 1 and C["saturation"] == 1: return img
        out = cv2.LUT(img, self._lut(C))
        if C["saturation"] != 1.0:
            g = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            out = cv2.addWeighted(out, C["saturation"], g, 1 - C["saturation"], 0)
        if C["glow"]:
            h, w = out.shape[:2]; sm = cv2.resize(out, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
            sm = cv2.GaussianBlur(sm, (0, 0), max(w, h) * 0.012 / 8)
            b = cv2.resize(sm, (w, h), interpolation=cv2.INTER_LINEAR)
            inv = cv2.multiply(255 - out, 255 - cv2.convertScaleAbs(b, alpha=C["glow"]), scale=1 / 255.0)
            out = 255 - inv
        return out

    def apply(self, img):
        P0 = self.P; h, w = img.shape[:2]
        need_face = any(P0["face"].values()) or any(v for k, v in P0["skin"].items() if k != "lip_lab")
        lm = self._landmarks(img) if need_face else None
        g = getattr(self, "gain", 1.0) if lm is not None else 0.0
        P = dict(P0); P["face"] = {k: v * g for k, v in P0["face"].items()}; P["body"] = {k: v * g for k, v in P0["body"].items()}
        P["skin"] = {k: (v * g if k != "lip_lab" else v) for k, v in P0["skin"].items()}
        need_body = self.pose is not None and lm is not None  # chỉ chỉnh dáng khi thấy mặt Pum trong khung
        if (lm is not None and any(P["face"].values())) or need_body:
            sc = 4; gx, gy = np.meshgrid(np.arange(0, w, sc, np.float32), np.arange(0, h, sc, np.float32))
            ux, uy = np.zeros_like(gx), np.zeros_like(gy)
            if lm is not None and any(P["face"].values()):
                a, b = self._face_field(lm, gx, gy, P["face"]); ux += a; uy += b
            if need_body:
                a, b = self._body_field(img, gx, gy, P["body"]); ux += a; uy += b
            if np.abs(ux).max() > 0.05 or np.abs(uy).max() > 0.05:
                mx = cv2.resize(gx + ux, (w, h), interpolation=cv2.INTER_LINEAR); my = cv2.resize(gy + uy, (w, h), interpolation=cv2.INTER_LINEAR)
                img = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if lm is not None and any(v for k, v in P["skin"].items() if k != "lip_lab"):
            S = dict(P["skin"])
            fw = np.ptp(lm[:, 0]); c = lm.mean(0).astype(int)
            patch = img[max(0, c[1] - int(fw * .2)):c[1] + int(fw * .2), max(0, c[0] - int(fw * .2)):c[0] + int(fw * .2)]
            if patch.size and patch.mean() < 95:  # cảnh tối: da dễ đỏ, giảm hồng
                S["rosy"] = S.get("rosy", 0) * 0.45; S["blush"] = S.get("blush", 0) * 0.5; S["lips"] = S.get("lips", 0) * 0.7
            img = img.copy(); self._skin(img, lm, S)
        return self._color(img, P["color"])


# ---------- đo video mẫu ----------
def measure(paths, every=1.0):
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    fl = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MD / "face_landmarker.task")), num_faces=1))
    rows = []
    for p in paths:
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))
        t = 0.3
        while t < d:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", p, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
            t += every
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
            if img is None: continue
            h, w = img.shape[:2]
            r = fl.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            if not r.face_landmarks: continue
            lm = np.array([[l.x * w, l.y * h] for l in r.face_landmarks[0]]); fw = np.linalg.norm(lm[234] - lm[454])
            if fw < 0.15 * w: continue
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(float); hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(float)
            sk = np.vstack([lab[int(lm[i][1]) - 6:int(lm[i][1]) + 6, int(lm[i][0]) - 6:int(lm[i][0]) + 6].reshape(-1, 3) for i in (50, 280, 9)])
            rows.append(dict(
                skinL=sk[:, 0].mean(), skinA=sk[:, 1].mean(), skinB=sk[:, 2].mean(), L=lab[..., 0].mean(), Lsd=lab[..., 0].std(),
                p5=np.percentile(lab[..., 0], 5), p95=np.percentile(lab[..., 0], 95), sat=hsv[..., 1].mean(),
                jaw=np.linalg.norm(lm[172] - lm[397]) / fw, chin=np.linalg.norm(lm[152] - lm[17]) / fw,
                eyeW=(np.linalg.norm(lm[33] - lm[133]) + np.linalg.norm(lm[362] - lm[263])) / 2 / fw,
                length=np.linalg.norm(lm[10] - lm[152]) / fw))
    if not rows: return {}
    keys = rows[0].keys(); return {k: round(float(np.median([r[k] for r in rows])), 3) for k in keys} | {"n": len(rows)}


def run_video(preset, src, dst, ss=None, to=None, side=False):
    B = Beauty(preset)
    w, h = [int(x) for x in subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src]).decode().strip().split(",")[:2]]
    cut = (["-ss", str(ss)] if ss is not None else []) + (["-to", str(to)] if to is not None else [])
    rd = subprocess.Popen(["ffmpeg", "-v", "error", *cut, "-i", src, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    W = w * 2 if side else w
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{h}", "-r", "30", "-i", "-", *cut, "-i", src,
                           "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", dst], stdin=subprocess.PIPE)
    fs = w * h * 3
    while True:
        b = rd.stdout.read(fs)
        if len(b) < fs: break
        img = np.frombuffer(b, np.uint8).reshape(h, w, 3).copy(); o = B.apply(img)
        wr.stdin.write((np.hstack([img, o]) if side else o).tobytes())
    wr.stdin.close(); wr.wait()


if __name__ == "__main__":
    if sys.argv[1] == "measure":
        print(json.dumps(measure(sys.argv[2:]), ensure_ascii=False))
    else:
        a = sys.argv; pre = json.load(open(a[1]))
        ss = float(a[a.index("--ss") + 1]) if "--ss" in a else None; to = float(a[a.index("--to") + 1]) if "--to" in a else None
        run_video(pre, a[2], a[3], ss, to, "--side" in a)
