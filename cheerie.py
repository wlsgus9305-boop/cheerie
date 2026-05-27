#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""Cheerie — a tiny desktop cheer cat."""

# ── DPI 인식 (가장 먼저 설정) ──
import ctypes
try:    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

import sys, os, math, time, json, threading, datetime, re
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from pynput import keyboard as pynput_kb, mouse as pynput_ms
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


# ════════════════════════════════════════════════════════
#  경로 / 상수
# ════════════════════════════════════════════════════════
BASE_DIR    = (os.path.dirname(sys.executable)
               if getattr(sys, "frozen", False)
               else os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "cheerie_config.json")
CONFIG_REG_KEY = r"Software\Cheerie"
CHROMA      = (0, 255, 0)
CHROMA_HEX  = "#00FF00"

# 게이지 설정
G_UP_KEY    = 8.0
G_UP_CLICK  = 4.0
G_DECAY_HI  = 28.0
G_DECAY_LO  = 12.0
G_CHEER     = 50.0
G_HOT       = 560.0
G_MAX       = 610.0
HOT_TIMEOUT = 1.15
HOT_DROP_TO = 110.0

# 공통 팔레트
C = {
    "bg"  : "#0d1117",
    "bg2" : "#161b22",
    "bg3" : "#21262d",
    "bdr" : "#30363d",
    "fg"  : "#e6edf3",
    "fg2" : "#8b949e",
    "acc" : "#1f6feb",
    "acc2": "#388bfd",
    "red" : "#ff7b72",
    "on"  : "#162032",
}

DEFAULT_ALARM_TIME = "17:00"
MAX_ALARMS = 6
DEFAULT_MESSAGES = {
    "en": "Take a break",
    "ko": "쉬는 시간!",
}

DEFAULT_CFG = {
    "language": "en",
    "alarms"  : [{"time": DEFAULT_ALARM_TIME, "message": DEFAULT_MESSAGES["en"]}],
    "flip_h"  : False,
    "flip_v"  : False,
}

TEXT = {
    "en": {
        "settings": "Settings",
        "flip_h": "Flip horizontal",
        "flip_v": "Flip vertical",
        "test_alarm": "Test alarm",
        "quit": "Quit",
        "save": "Save",
        "language": "Language",
        "alarms": "Alarms",
        "alarm": "Alarm",
        "message": "Message",
        "add_alarm": "+ Add alarm",
        "time_hint": "Digits only  (ex: 930 -> 09:30, 1700 -> 17:00)",
        "time_error": "Use a valid time between 00:00 and 23:59",
        "alarm_title": "Alarm",
        "alarm_heading": "Alarm time!",
        "ok": "OK",
        "test_alarm_message": "Test alarm",
    },
    "ko": {
        "settings": "설정",
        "flip_h": "좌우 반전",
        "flip_v": "상하 반전",
        "test_alarm": "알람 테스트",
        "quit": "종료",
        "save": "저  장",
        "language": "언어",
        "alarms": "알람",
        "alarm": "알람",
        "message": "내용",
        "add_alarm": "+ 알람 추가",
        "time_hint": "숫자만 입력 가능  (예: 930 -> 09:30, 1700 -> 17:00)",
        "time_error": "00:00~23:59 사이로 입력해주세요",
        "alarm_title": "알림",
        "alarm_heading": "알람 시간이에요!",
        "ok": "확인",
        "test_alarm_message": "테스트 알람",
    },
}

def lang_code(cfg=None):
    code = (cfg or load_cfg()).get("language", "en")
    return code if code in TEXT else "en"

def tr(key, cfg=None):
    code = lang_code(cfg)
    return TEXT.get(code, TEXT["en"]).get(key, TEXT["en"].get(key, key))

def _to_bool(value):
    return str(value).lower() in ("1", "true", "yes", "on")

def _default_alarm(language="en"):
    return {
        "time": DEFAULT_ALARM_TIME,
        "message": DEFAULT_MESSAGES.get(language, DEFAULT_MESSAGES["en"]),
    }

def _normalize_alarm(alarm, language="en"):
    if isinstance(alarm, dict):
        alarm_time = str(alarm.get("time") or alarm.get("alarm_time") or "").strip()
        message = str(alarm.get("message") or "").strip()
    else:
        alarm_time = str(alarm).strip()
        message = ""
    if not is_valid_time(alarm_time):
        return None
    if not message:
        message = DEFAULT_MESSAGES.get(language, DEFAULT_MESSAGES["en"])
    return {"time": alarm_time, "message": message[:80]}

def _normalize_alarms(value, language="en"):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = [{"time": value}]
    if isinstance(value, dict):
        value = [value]
    alarms = []
    if isinstance(value, list):
        for alarm in value:
            normalized = _normalize_alarm(alarm, language)
            if normalized:
                alarms.append(normalized)
    return (alarms or [_default_alarm(language)])[:MAX_ALARMS]

def _decode_cfg_value(value, default):
    if isinstance(default, bool):
        return _to_bool(value)
    if isinstance(default, list):
        try:
            return json.loads(value)
        except Exception:
            return default
    return str(value)

def _load_registry_cfg():
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONFIG_REG_KEY) as key:
            data = {}
            for name, default in DEFAULT_CFG.items():
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except OSError:
                    continue
                data[name] = _decode_cfg_value(value, default)
            if "alarms" not in data:
                try:
                    value, _ = winreg.QueryValueEx(key, "alarm_time")
                    data["alarms"] = [{"time": str(value), "message": ""}]
                except OSError:
                    pass
            return data
    except OSError:
        pass
    return None

def load_cfg():
    d = DEFAULT_CFG.copy()
    d["alarms"] = [a.copy() for a in DEFAULT_CFG["alarms"]]
    reg = _load_registry_cfg()
    if reg is not None:
        d.update(reg)
        d["language"] = lang_code(d)
        d["alarms"] = _normalize_alarms(d.get("alarms"), d["language"])
        return d

    # JSON fallback for non-Windows environments.
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            old = json.load(f)
        d["language"] = old.get("language", d["language"])
        if "alarms" in old:
            d["alarms"] = old["alarms"]
        elif "alarm_time" in old:
            d["alarms"] = [{"time": old["alarm_time"], "message": old.get("alarm_message", "")}]
        elif "checkout_time" in old:
            d["alarms"] = [{"time": old["checkout_time"], "message": old.get("alarm_message", "")}]
        d["flip_h"] = old.get("flip_h", d["flip_h"])
        d["flip_v"] = old.get("flip_v", d["flip_v"])
        d["language"] = lang_code(d)
        d["alarms"] = _normalize_alarms(d.get("alarms"), d["language"])
        if sys.platform == "win32":
            save_cfg(d)
        return d
    except Exception:
        return d

def save_cfg(data):
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIG_REG_KEY) as key:
                for name, default in DEFAULT_CFG.items():
                    value = data.get(name, default)
                    if isinstance(default, bool):
                        value = "1" if value else "0"
                    elif isinstance(default, list):
                        value = json.dumps(value, ensure_ascii=False)
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
            return
        except OSError:
            pass
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception: pass

def is_valid_time(value):
    if not re.match(r"^\d{1,2}:\d{2}$", value):
        return False
    try:
        h, m = map(int, value.split(":"))
    except ValueError:
        return False
    return 0 <= h <= 23 and 0 <= m <= 59

def get_img(filename):
    for folder in [BASE_DIR, os.path.join(BASE_DIR, "images")]:
        p = os.path.join(folder, filename)
        if os.path.isfile(p): return p
    if getattr(sys, "frozen", False):
        p = os.path.join(sys._MEIPASS, filename)
        if os.path.isfile(p): return p
    return None


# ════════════════════════════════════════════════════════
#  이미지 로더
# ════════════════════════════════════════════════════════
def _remove_bg(img: Image.Image, tol: int = 80) -> Image.Image:
    rgba = img.convert("RGBA")
    w, h = rgba.size
    for corner in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]:
        if rgba.getpixel(corner)[3] == 0: continue
        ImageDraw.floodfill(rgba, corner, (0, 0, 0, 0), thresh=tol)
    return rgba

def load_photo(path, max_w, max_h, flip_h=False, flip_v=False, chroma_bg=True):
    raw = Image.open(path)
    raw = _remove_bg(raw, tol=80)
    raw.thumbnail((max_w, max_h), Image.LANCZOS)
    if flip_h: raw = raw.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v: raw = raw.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = raw.split()
    a = a.point(lambda x: 255 if x >= 128 else 0)
    raw = Image.merge("RGBA", (r, g, b, a))
    if not chroma_bg:
        return ImageTk.PhotoImage(raw)
    bg = Image.new("RGB", raw.size, CHROMA)
    bg.paste(raw.convert("RGB"), mask=raw.split()[3])
    return ImageTk.PhotoImage(bg)


# ════════════════════════════════════════════════════════
#  폴백 드로어
# ════════════════════════════════════════════════════════
class FallbackDrawer:
    Y="#FFD700";DY="#C8A000";BK="#111"
    def __init__(self,c,cx,cy,sc=1.0):
        self.c=c;self.cx=cx;self.cy=cy;self.sc=sc;self._ids=[]
    def _s(self,v): return v*self.sc
    def _xy(self,x,y): return self.cx+self._s(x),self.cy+self._s(y)
    def _oval(self,x1,y1,x2,y2,**kw):
        a,b=self._xy(x1,y1);c,d=self._xy(x2,y2)
        i=self.c.create_oval(a,b,c,d,**kw);self._ids.append(i)
    def _poly(self,pts,**kw):
        sp=[]
        for k in range(0,len(pts),2):
            ax,ay=self._xy(pts[k],pts[k+1]);sp+=[ax,ay]
        i=self.c.create_polygon(sp,**kw);self._ids.append(i)
    def _arc(self,x1,y1,x2,y2,**kw):
        a,b=self._xy(x1,y1);c,d=self._xy(x2,y2)
        i=self.c.create_arc(a,b,c,d,**kw);self._ids.append(i)
    def _text(self,x,y,**kw):
        ax,ay=self._xy(x,y);i=self.c.create_text(ax,ay,**kw);self._ids.append(i)
    def clear(self):
        for i in self._ids: self.c.delete(i)
        self._ids.clear()
    def draw(self,state,t):
        self.clear()
        if   state=="idle":  dy=math.sin(t*1.8)*2.5;ey="n"
        elif state=="cheer": dy=abs(math.sin(t*4.5))*-10;ey="h"
        elif state in("cheerhot","alarm"): dy=abs(math.sin(t*6))*-14;ey="h"
        elif state=="happy": dy=math.sin(t*3)*3;ey="h"
        else: dy=0;ey="n"
        au=state in("cheer","cheerhot","alarm","happy")
        self._poly([20,42+dy,32,28+dy,27,22+dy,42,10+dy,36,4+dy,50,-10+dy,
                    40,-7+dy,34,-22+dy,24,-13+dy,34,-3+dy,18,14+dy,26,19+dy,16,34+dy],
                   fill=self.Y,outline=self.DY,width=2)
        self._oval(-27,28+dy,27,70+dy,fill=self.Y,outline=self.DY,width=2)
        if au:
            la=math.sin(t*5)*7;ra=-math.sin(t*5)*7
            self._oval(-50,8+dy-20+la,-28,26+dy-20+la,fill=self.Y,outline=self.DY,width=2)
            self._oval(28,8+dy-20+ra,50,26+dy-20+ra,fill=self.Y,outline=self.DY,width=2)
        else:
            self._oval(-50,28+dy,-28,46+dy,fill=self.Y,outline=self.DY,width=2)
            self._oval(28,28+dy,50,46+dy,fill=self.Y,outline=self.DY,width=2)
        self._oval(-34,-44+dy,34,34+dy,fill=self.Y,outline=self.DY,width=2)
        self._poly([-30,-44+dy,-22,-80+dy,-8,-44+dy],fill=self.Y,outline=self.DY,width=2)
        self._poly([-28,-54+dy,-22,-80+dy,-9,-54+dy],fill=self.BK,outline="")
        self._poly([8,-44+dy,22,-80+dy,30,-44+dy],fill=self.Y,outline=self.DY,width=2)
        self._poly([9,-54+dy,22,-80+dy,28,-54+dy],fill=self.BK,outline="")
        if ey=="h":
            self._arc(-22,-22+dy,-8,-10+dy,start=0,extent=180,style="arc",outline=self.BK,width=3)
            self._arc(8,-22+dy,22,-10+dy,start=0,extent=180,style="arc",outline=self.BK,width=3)
        else:
            self._oval(-22,-22+dy,-8,-8+dy,fill=self.BK,outline="")
            self._oval(8,-22+dy,22,-8+dy,fill=self.BK,outline="")
        if state=="alarm":
            self._text(0,-100,text="ALARM!",fill="#FF2222",font=("맑은 고딕",12,"bold"))


# ════════════════════════════════════════════════════════
#  캐릭터 스프라이트
# ════════════════════════════════════════════════════════
class CharacterSprite:
    IMG_W, IMG_H = 185, 210

    def __init__(self, canvas, cx, cy, flip_h=False, flip_v=False, chroma_bg=True):
        self.c=canvas; self.cx=cx; self.cy=cy
        self.flip_h=flip_h; self.flip_v=flip_v; self.chroma_bg=chroma_bg
        self._photos={}; self._img_item=None
        self._fx=[]; self._fallback=None
        self._load()

    def _load(self):
        if not HAS_PIL:
            self._fallback=FallbackDrawer(self.c,self.cx,self.cy); return
        def _lp(fn):
            p=get_img(fn)
            if not p: return None
            try: return load_photo(p,self.IMG_W,self.IMG_H,self.flip_h,self.flip_v,self.chroma_bg)
            except Exception as e: print(f"이미지 오류 {fn}: {e}"); return None
        idle_ph=_lp("idle.png"); cheer_ph=_lp("cheer.png")
        happy_ph=_lp("happy.png"); hot1_ph=_lp("cheerhot1.png"); hot2_ph=_lp("cheerhot2.png")
        if not idle_ph:
            self._fallback=FallbackDrawer(self.c,self.cx,self.cy); return
        self._photos["idle"]    =[idle_ph]
        self._photos["cheer"]   =[p for p in [idle_ph,cheer_ph] if p]
        self._photos["happy"]   =[p for p in [happy_ph,cheer_ph] if p]
        self._photos["cheerhot"]=[p for p in [hot1_ph,hot2_ph] if p]
        self._photos["alarm"]   =[p for p in [hot1_ph,hot2_ph] if p]
        if self._img_item is None:
            self._img_item=self.c.create_image(self.cx,self.cy,image=idle_ph,anchor="center")
        else:
            self.c.itemconfig(self._img_item, image=idle_ph)

    def reload(self, flip_h, flip_v):
        self.flip_h=flip_h; self.flip_v=flip_v
        self._photos={}; self._fallback=None; self._load()

    def _clr_fx(self):
        for i in self._fx: self.c.delete(i)
        self._fx.clear()

    def _star(self, x, y, sz, fill, outline):
        if self.flip_h: x=-x
        if self.flip_v: y=-y
        pts=[]
        for j in range(5):
            a=math.radians(j*72-90)
            pts.extend([self.cx+x+math.cos(a)*sz, self.cy+y+math.sin(a)*sz])
            a=math.radians(j*72+36-90)
            pts.extend([self.cx+x+math.cos(a)*sz*.4, self.cy+y+math.sin(a)*sz*.4])
        if pts:
            i=self.c.create_polygon(pts,fill=fill,outline=outline,width=1)
            self._fx.append(i)

    def _heart(self, x, y, r=8):
        if self.flip_h: x=-x
        if self.flip_v: y=-y
        pts=[]
        for deg in range(0,360,18):
            a=math.radians(deg)
            hx=r*16*(math.sin(a)**3)
            hy=-r*(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))
            pts.extend([self.cx+x+hx/16, self.cy+y+hy/16])
        if len(pts)>=4:
            i=self.c.create_polygon(pts,fill="#FF69B4",outline=""); self._fx.append(i)

    def draw(self, state, t, gauge=0.0):
        if self._fallback: self._fallback.draw(state,t); return
        self._clr_fx()
        frames=self._photos.get(state) or self._photos.get("idle",[])
        if not frames: return
        if state in ("cheer","cheerhot","alarm") and len(frames)>1:
            fi=int(t*(4.5 if state in("cheerhot","alarm") else 3.0))%len(frames)
        else: fi=0
        if   state=="idle":                dy=math.sin(t*1.8)*3
        elif state=="cheer":               dy=abs(math.sin(t*4.5))*-10
        elif state in("cheerhot","alarm"): dy=abs(math.sin(t*6))*-14
        else:                              dy=0
        self.c.itemconfig(self._img_item, image=frames[fi])
        self.c.coords(self._img_item, self.cx, self.cy+dy)
        cheer_amt = max(0.0, min(1.0, (gauge - G_CHEER) / max(1.0, G_HOT - G_CHEER)))
        hot_amt = max(0.0, min(1.0, (gauge - G_HOT) / max(1.0, G_MAX - G_HOT)))
        if state=="happy":
            for i in range(3):
                off=i*2.09
                hx=math.sin(t+off)*50; hy=-90-((t*20+i*18)%60)
                if -130<hy<-30: self._heart(hx,hy)
        elif state=="cheer":
            count = 2 + int(cheer_amt * 2.8)
            for i in range(count):
                off=i*(math.tau/max(1,count))
                self._star(math.cos(t*1.55+off)*58,math.sin(t*1.55+off)*30-48,
                           5.5+math.sin(t*2.1+off)*1.3,"#FFD84A","#E3A018")
        elif state in("cheerhot","alarm"):
            count = 4 + int(hot_amt * 2.0)
            for i in range(count):
                off=i*(math.tau/max(1,count))
                self._star(math.cos(t*2.7+off)*68,math.sin(t*2.7+off)*36-50,
                           7.5+math.sin(t*3.7+off)*2.0,"#FF3030","#FF8585")
            if math.sin(t*5.5)>0.45:
                rd=88+hot_amt*18; v=120
                i=self.c.create_oval(self.cx-rd,self.cy-rd,self.cx+rd,self.cy+rd,
                                     outline=f"#{v:02x}0000",width=2,fill="")
                self._fx.append(i)
            if state=="alarm":
                i=self.c.create_text(self.cx,self.cy-120,text="ALARM!",
                                      fill="#FF2222",font=("맑은 고딕",13,"bold"))
                self._fx.append(i)


# ════════════════════════════════════════════════════════
#  우클릭 메뉴
# ════════════════════════════════════════════════════════
class ActionPanel(tk.Toplevel):
    def __init__(self, parent, rx, ry, cbs, checked=None, cfg=None):
        super().__init__(parent)
        ck = checked or {}
        cfg = cfg or load_cfg()

        ITEMS = [
            ("↔",  tr("flip_h", cfg),      "flip_h",      ck.get("flip_h", False)),
            ("↕",  tr("flip_v", cfg),      "flip_v",      ck.get("flip_v", False)),
            ("─",  None,            None,          False),
            ("⚙",  tr("settings", cfg),    "settings",    False),
            ("─",  None,            None,          False),
            ("🔔", tr("test_alarm", cfg),  "test_alarm",  False),
            ("✕",  tr("quit", cfg),        "quit",        False),
        ]

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=C["bdr"])

        W=220; ROW=34; SEP=10; PAD=6
        H = PAD*2 + sum(SEP if lbl is None else ROW for _,lbl,_,_ in ITEMS) + 2
        sw,sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = min(rx, sw-W-8)
        y = (max(8, ry-H) if ry+H > sh-80 else min(ry, sh-H-8))
        self.geometry(f"{W}x{H}+{x}+{y}")

        cv = tk.Canvas(self, width=W, height=H, bg=C["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=1, pady=1)

        ypos = PAD
        for icon, label, key, is_on in ITEMS:
            if label is None:
                cv.create_line(10, ypos+SEP//2, W-12, ypos+SEP//2, fill=C["bdr"])
                ypos += SEP; continue
            y1, y2 = ypos, ypos+ROW; tag = f"i_{key}"
            base = C["on"] if is_on else C["bg2"]
            rect = cv.create_rectangle(4, y1+2, W-4, y2-2, fill=base, outline="", tags=tag)
            cv.create_text(22, (y1+y2)//2, text=icon,
                           font=("Segoe UI Emoji", 11), fill=C["fg"],
                           anchor="center", tags=tag)
            lbl_col = C["red"] if key=="quit" else (C["acc"] if is_on else C["fg"])
            cv.create_text(40, (y1+y2)//2, text=label,
                           font=("맑은 고딕", 10), fill=lbl_col,
                           anchor="w", tags=tag)
            if is_on:
                cv.create_text(W-12, (y1+y2)//2, text="●",
                               font=("맑은 고딕", 9), fill=C["acc"],
                               anchor="center", tags=tag)
            def _bind(tag=tag, rect=rect, key=key, base=base):
                cv.tag_bind(tag, "<Enter>",
                    lambda e, r=rect: cv.itemconfig(r, fill=C["acc"]))
                cv.tag_bind(tag, "<Leave>",
                    lambda e, r=rect, b=base: cv.itemconfig(r, fill=b))
                cv.tag_bind(tag, "<Button-1>",
                    lambda e, k=key: (self.destroy(), cbs.get(k) and cbs[k]()))
            _bind()
            ypos += ROW

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(20, self.focus_force)


# ════════════════════════════════════════════════════════
#  설정 창 (알람 시간만)
# ════════════════════════════════════════════════════════
class SettingsWindow(tk.Toplevel):
    W = 460

    def __init__(self, parent, cfg, on_save=None):
        super().__init__(parent)
        self.cfg = cfg.copy(); self.on_save = on_save
        self._fmt_busy = False; self._drag_ref = None
        self.lang_v = tk.StringVar(value=lang_code(self.cfg))
        self.alarm_rows = []
        self._wrap = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=C["bdr"])

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x100+{(sw-self.W)//2}+{(sh-100)//2}")
        self._build()
        self.update_idletasks()
        H = min(self.winfo_reqheight() + 2, sh - 60)
        self.geometry(f"{self.W}x{H}+{(sw-self.W)//2}+{(sh-H)//2}")
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(60, self.focus_force)

    def _build(self):
        W = self.W
        if self._wrap and self._wrap.winfo_exists():
            self._wrap.destroy()
        self.alarm_rows = []
        wrap = tk.Frame(self, bg=C["bg"])
        self._wrap = wrap
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        hdr = tk.Frame(wrap, bg=C["bg2"], height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        self._bind_drag(hdr)
        title = tk.Label(hdr, text=f"⚙  {tr('settings', self.cfg)}",
                         bg=C["bg2"], fg=C["fg"],
                         font=("맑은 고딕", 11, "bold"))
        title.pack(side="left", padx=16); self._bind_drag(title)
        x_btn = tk.Label(hdr, text="✕", bg=C["bg2"], fg=C["fg2"],
                         font=("맑은 고딕", 12), cursor="hand2", padx=14)
        x_btn.pack(side="right")
        x_btn.bind("<Enter>",    lambda e: x_btn.config(bg="#2d1416", fg=C["red"]))
        x_btn.bind("<Leave>",    lambda e: x_btn.config(bg=C["bg2"],  fg=C["fg2"]))
        x_btn.bind("<Button-1>", lambda e: self.destroy())
        tk.Frame(wrap, bg=C["bdr"], height=1).pack(fill="x")

        tk.Frame(wrap, bg=C["bdr"], height=1).pack(fill="x", side="bottom")
        save_cv = tk.Canvas(wrap, bg=C["acc"], height=44,
                            highlightthickness=0, cursor="hand2")
        save_cv.pack(fill="x", side="bottom")
        save_cv.create_text(W//2, 22, text=tr("save", self.cfg),
                            fill=C["fg"], font=("맑은 고딕", 11, "bold"))
        save_cv.bind("<Enter>",    lambda e: save_cv.config(bg=C["acc2"]))
        save_cv.bind("<Leave>",    lambda e: save_cv.config(bg=C["acc"]))
        save_cv.bind("<Button-1>", lambda e: self._save())

        body = tk.Frame(wrap, bg=C["bg"]); body.pack(fill="both", expand=True)

        self._sec(body, tr("language", self.cfg))
        lang_card = self._card(body)
        lang_row = tk.Frame(lang_card, bg=C["bg2"])
        lang_row.pack(anchor="w", padx=14, pady=8)
        for code, label in [("en", "English"), ("ko", "한국어")]:
            tk.Radiobutton(lang_row, text=label, variable=self.lang_v, value=code,
                           bg=C["bg2"], fg=C["fg"], selectcolor=C["bg3"],
                           activebackground=C["bg2"], activeforeground=C["acc"],
                           font=("맑은 고딕", 10),
                           command=self._on_language_change).pack(side="left", padx=(0, 16))

        self._sec(body, tr("alarms", self.cfg))
        self.alarm_card = self._card(body)
        self.rows_frame = tk.Frame(self.alarm_card, bg=C["bg2"])
        self.rows_frame.pack(fill="x")
        for alarm in _normalize_alarms(self.cfg.get("alarms"), lang_code(self.cfg)):
            self._add_alarm_row(alarm)
        tk.Label(self.alarm_card, text=tr("time_hint", self.cfg),
                 bg=C["bg2"], fg=C["fg2"], font=("맑은 고딕", 8)
                 ).pack(anchor="w", padx=14, pady=(4, 10))
        add_btn = tk.Label(self.alarm_card, text=tr("add_alarm", self.cfg),
                           bg=C["bg3"], fg=C["acc"], font=("맑은 고딕", 9, "bold"),
                           cursor="hand2", padx=10, pady=6)
        add_btn.pack(anchor="w", padx=14, pady=(0, 12))
        add_btn.bind("<Button-1>", lambda e: self._add_alarm_row())

        self._err = tk.Label(body, text="", bg=C["bg"], fg=C["red"],
                             font=("맑은 고딕", 9))
        self._err.pack(pady=(2, 0))

    def _sec(self, parent, title):
        f = tk.Frame(parent, bg=C["bg"]); f.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(f, text=title, bg=C["bg"], fg=C["fg2"],
                 font=("맑은 고딕", 9, "bold")).pack(side="left")
        tk.Frame(f, bg=C["bg3"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _card(self, parent):
        f = tk.Frame(parent, bg=C["bg2"]); f.pack(fill="x", padx=16, pady=2); return f

    def _resize_to_content(self):
        self.update_idletasks()
        sh = self.winfo_screenheight()
        h = min(self.winfo_reqheight() + 2, sh - 60)
        self.geometry(f"{self.W}x{h}+{self.winfo_x()}+{self.winfo_y()}")

    def _snapshot_alarms(self):
        alarms = []
        for row in self.alarm_rows:
            alarms.append({
                "time": row["time"].get().strip() or DEFAULT_ALARM_TIME,
                "message": row["message"].get().strip(),
            })
        return alarms or _normalize_alarms(self.cfg.get("alarms"), self.lang_v.get())

    def _on_language_change(self):
        language = self.lang_v.get() if self.lang_v.get() in TEXT else "en"
        self.cfg["language"] = language
        self.cfg["alarms"] = self._snapshot_alarms()
        self._build()
        self._resize_to_content()

    def _add_alarm_row(self, alarm=None):
        if len(self.alarm_rows) >= MAX_ALARMS:
            self._err.config(text=f"Max {MAX_ALARMS} alarms")
            self.after(1800, lambda: self._err.config(text=""))
            return
        alarm = alarm or _default_alarm(self.lang_v.get())
        row = tk.Frame(self.rows_frame, bg=C["bg2"])
        row.pack(fill="x", padx=14, pady=(8 if not self.alarm_rows else 4, 0))
        time_v = tk.StringVar(value=alarm.get("time", DEFAULT_ALARM_TIME))
        msg_v = tk.StringVar(value=alarm.get("message", DEFAULT_MESSAGES["en"]))
        tk.Label(row, text=tr("alarm", self.cfg), bg=C["bg2"], fg=C["fg2"],
                 font=("맑은 고딕", 9), width=6, anchor="w").pack(side="left")
        time_e = tk.Entry(row, textvariable=time_v, width=6,
                          bg=C["bg3"], fg=C["acc"], insertbackground=C["acc"],
                          relief="flat", font=("Consolas", 11), bd=4,
                          justify="center")
        time_e.pack(side="left")
        time_e.bind("<FocusOut>", lambda ev, v=time_v: self._normalize_time(v))
        tk.Label(row, text=tr("message", self.cfg), bg=C["bg2"], fg=C["fg2"],
                 font=("맑은 고딕", 9)).pack(side="left", padx=(12, 4))
        msg_e = tk.Entry(row, textvariable=msg_v, width=26,
                         bg=C["bg3"], fg=C["fg"], insertbackground=C["fg"],
                         relief="flat", font=("맑은 고딕", 10), bd=4)
        msg_e.pack(side="left", fill="x", expand=True)
        del_btn = tk.Label(row, text="✕", bg=C["bg2"], fg=C["fg2"],
                           font=("맑은 고딕", 11), cursor="hand2", padx=8)
        del_btn.pack(side="left", padx=(6, 0))
        item = {"frame": row, "time": time_v, "message": msg_v}
        self.alarm_rows.append(item)
        time_v.trace_add("write", lambda *_, v=time_v: self._fmt_time(v))
        del_btn.bind("<Button-1>", lambda e, item=item: self._remove_alarm_row(item))
        self._resize_to_content()

    def _remove_alarm_row(self, item):
        if item in self.alarm_rows:
            self.alarm_rows.remove(item)
            item["frame"].destroy()
        if not self.alarm_rows:
            self._add_alarm_row(_default_alarm(self.lang_v.get()))
        self._resize_to_content()

    def _bind_drag(self, w):
        w.bind("<ButtonPress-1>", self._drag_start)
        w.bind("<B1-Motion>",     self._drag_move)

    def _drag_start(self, e):
        self._drag_ref = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e):
        if self._drag_ref:
            ox, oy = self._drag_ref
            self.geometry(f"+{e.x_root-ox}+{e.y_root-oy}")

    def _fmt_time(self, var):
        if self._fmt_busy: return
        self._fmt_busy = True
        try:
            d = ''.join(c for c in var.get() if c.isdigit())
            if len(d) >= 4: var.set(f"{d[:2]}:{d[2:4]}")
        finally: self._fmt_busy = False

    def _normalize_time(self, var):
        if self._fmt_busy: return
        self._fmt_busy = True
        try:
            d = ''.join(c for c in var.get().strip() if c.isdigit())
            if len(d) == 3: var.set(f"0{d[0]}:{d[1:3]}")
            elif len(d) >= 4: var.set(f"{d[:2]}:{d[2:4]}")
        finally: self._fmt_busy = False

    def _save(self):
        language = self.lang_v.get() if self.lang_v.get() in TEXT else "en"
        alarms = []
        for row in self.alarm_rows:
            alarm_time = row["time"].get().strip()
            if not is_valid_time(alarm_time):
                self._err.config(text=tr("time_error", {"language": language}))
                self.after(2500, lambda: self._err.config(text="")); return
            message = row["message"].get().strip() or DEFAULT_MESSAGES.get(language, DEFAULT_MESSAGES["en"])
            alarms.append({"time": alarm_time, "message": message[:80]})
        c = load_cfg()
        c["language"] = language
        c["alarms"] = alarms
        save_cfg(c)
        if self.on_save: self.on_save(c)
        self.destroy()


# ════════════════════════════════════════════════════════
#  알람 팝업
# ════════════════════════════════════════════════════════
class AlarmWindow(tk.Toplevel):
    def __init__(self, parent, on_done, alarm=None):
        super().__init__(parent)
        self.on_done = on_done
        cfg = load_cfg()
        alarm = _normalize_alarm(alarm or _default_alarm(lang_code(cfg)), lang_code(cfg)) or _default_alarm(lang_code(cfg))
        self.title(tr("alarm_title", cfg))
        self.configure(bg=C["bg"]); self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = 380, 360
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        cv = tk.Canvas(self, width=w, height=h, bg=C["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True)
        self.sprite = CharacterSprite(cv, cx=190, cy=190,
                                      flip_h=cfg.get("flip_h", False),
                                      flip_v=cfg.get("flip_v", False),
                                      chroma_bg=False)
        cv.create_text(190, 30, text=tr("alarm_heading", cfg),
                       fill="#FFD700", font=("맑은 고딕", 16, "bold"))
        cv.create_text(190, 56, text=f"{alarm['time']}  {alarm['message']}",
                       fill=C["fg2"], font=("맑은 고딕", 10), width=320)
        bf = tk.Frame(cv, bg=C["bg"]); cv.create_window(190, 326, window=bf)
        tk.Button(bf, text=tr("ok", cfg), bg=C["acc"], fg=C["fg"],
                  font=("맑은 고딕", 12, "bold"), relief="flat",
                  cursor="hand2", padx=40, pady=8,
                  command=self._close).pack()
        self._t = 0.0; self._running = True; self._anim()

    def _anim(self):
        if not self._running: return
        self._t += 0.08; self.sprite.draw("alarm", self._t)
        self.after(50, self._anim)

    def _close(self):
        self._running = False
        if self.on_done: self.on_done()
        self.destroy()


# ════════════════════════════════════════════════════════
#  메인 앱 (공개용)
# ════════════════════════════════════════════════════════
class App:
    CW, CH = 200, 260

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cheerie")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", CHROMA_HEX)
        self.root.overrideredirect(True)
        self.root.configure(bg=CHROMA_HEX)

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{self.CW}x{self.CH}+{sw-self.CW-20}+{sh-self.CH-60}")

        self.cv = tk.Canvas(self.root, width=self.CW, height=self.CH,
                            bg=CHROMA_HEX, highlightthickness=0)
        self.cv.pack()

        cfg = load_cfg()
        self.sprite = CharacterSprite(self.cv, cx=self.CW//2, cy=self.CH//2+5,
                                      flip_h=cfg.get("flip_h", False),
                                      flip_v=cfg.get("flip_v", False))

        self.state          = "idle"
        self.t              = 0.0
        self._gauge         = 0.0
        self._visual_gauge  = 0.0
        self._forced_state  = None
        self._force_until   = 0.0
        self._lock          = threading.Lock()
        self._drag_xy       = None
        self._panel         = None
        self._last_key_time = time.time() - 999
        self._hot_drop      = False
        self._last_hover    = 0.0
        self._hovering      = False
        self._pressing      = False
        self._heart_job     = None

        self.cv.bind("<ButtonPress-1>",   self._lclick)
        self.cv.bind("<B1-Motion>",       self._drag)
        self.cv.bind("<ButtonRelease-1>", self._lrelease)
        self.cv.bind("<ButtonPress-3>",   self._rclick)
        self.cv.bind("<Motion>",          self._hover)
        self.cv.bind("<Enter>",           self._enter)
        self.cv.bind("<Leave>",           self._leave)

        if HAS_PYNPUT:
            kl = pynput_kb.Listener(on_press=self._kb); kl.daemon=True; kl.start()
            ml = pynput_ms.Listener(on_click=self._ms); ml.daemon=True; ml.start()

        threading.Thread(target=self._timer, daemon=True).start()
        self._anim()

    def _lclick(self, e):
        self._drag_xy = (e.x, e.y); self._moved = False
        self._pressing = True
        self._start_heart_loop()

    def _start_heart_loop(self):
        if self._heart_job is None:
            self._heart_repeat()

    def _heart_repeat(self):
        active_press = getattr(self, "_pressing", False) and not getattr(self, "_moved", False)
        with self._lock:
            alarm_active = self._forced_state == "alarm"
        if alarm_active:
            self._heart_job = None
            return
        if active_press or getattr(self, "_hovering", False):
            self._force("happy", 0.35)
            self._heart_job = self.root.after(90, self._heart_repeat)
        else:
            self._heart_job = None

    def _drag(self, e):
        if self._drag_xy:
            dx = e.x - self._drag_xy[0]; dy = e.y - self._drag_xy[1]
            if abs(dx)+abs(dy) > 3:
                self._moved = True
                self.root.geometry(
                    f"+{self.root.winfo_x()+dx}+{self.root.winfo_y()+dy}")

    def _lrelease(self, e):
        self._pressing = False; self._drag_xy = None
        if not getattr(self, "_moved", False):
            self._force("happy", 1.2)
        if self._hovering:
            self._start_heart_loop()

    def _enter(self, e):
        self._hovering = True
        self._start_heart_loop()

    def _leave(self, e):
        self._hovering = False

    def _rclick(self, e):
        if self._panel and self._panel.winfo_exists():
            self._panel.destroy(); return
        cfg = load_cfg()
        cbs = {
            "flip_h":     self._toggle_flip_h,
            "flip_v":     self._toggle_flip_v,
            "settings":   self._settings,
            "test_alarm": self._test_alarm,
            "quit":       self.root.quit,
        }
        checked = {"flip_h": cfg.get("flip_h", False), "flip_v": cfg.get("flip_v", False)}
        self._panel = ActionPanel(self.root,
                                  self.root.winfo_x() + e.x,
                                  self.root.winfo_y() + e.y,
                                  cbs, checked=checked, cfg=cfg)

    def _toggle_flip_h(self):
        c = load_cfg(); c["flip_h"] = not c.get("flip_h", False); save_cfg(c)
        self.sprite.reload(c["flip_h"], c.get("flip_v", False))

    def _toggle_flip_v(self):
        c = load_cfg(); c["flip_v"] = not c.get("flip_v", False); save_cfg(c)
        self.sprite.reload(c.get("flip_h", False), c["flip_v"])

    def _hover(self, e):
        now = time.time()
        self._hovering = True
        if self._drag_xy is not None: return
        if now - self._last_hover < 0.25: return
        with self._lock:
            if self._forced_state == "alarm": return
        self._last_hover = now
        self._start_heart_loop()

    def _kb(self, key):
        self._last_key_time = time.time(); self._hot_drop = False
        self._gauge = min(G_MAX, self._gauge + G_UP_KEY)

    def _ms(self, x, y, btn, pressed):
        if pressed:
            self._last_key_time = time.time(); self._hot_drop = False
            self._gauge = min(G_MAX, self._gauge + G_UP_CLICK)

    def _force(self, state, duration=2.0):
        with self._lock:
            self._forced_state = state
            self._force_until  = time.time() + duration

    def _anim(self):
        self.t += 0.07; dt = 0.05; now = time.time(); prev = self.state

        no_key = now - self._last_key_time
        if no_key < 0.3:
            decay = G_DECAY_HI if self._gauge > G_CHEER else G_DECAY_LO
        else:
            cool_accel = min(1.0, max(0.0, (no_key - 0.3) / 1.3))
            if self._gauge < G_HOT:
                decay = 34.0 + 56.0 * cool_accel
            else:
                decay = max(38.0, self._gauge / 2.6)
        self._gauge = max(0.0, self._gauge - decay*dt)

        if prev == "cheerhot" and no_key >= HOT_TIMEOUT:
            self._gauge = min(self._gauge, HOT_DROP_TO); self._hot_drop = True

        with self._lock:
            if self._forced_state and now < self._force_until:
                forced = self._forced_state
            else:
                self._forced_state = None; self._force_until = 0.0; forced = None

        if forced:               st = forced
        elif self._gauge>=G_HOT: st = "cheerhot"
        elif self._gauge>=G_CHEER: st = "cheer"
        else:                    st = "idle"

        self._visual_gauge += (self._gauge - self._visual_gauge) * 0.24
        self.state = st; self.sprite.draw(st, self.t, self._visual_gauge)
        self.root.after(50, self._anim)

    def _timer(self):
        fired = set(); last_day = ""
        while True:
            time.sleep(20)
            now = datetime.datetime.now(); today = now.date().isoformat()
            if today != last_day: fired.clear(); last_day = today
            c = load_cfg()
            for idx, alarm in enumerate(_normalize_alarms(c.get("alarms"), lang_code(c))):
                try:
                    h, m = map(int, alarm["time"].split(":"))
                    tgt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    diff = (now - tgt).total_seconds()
                    key = f"{idx}:{alarm['time']}:{alarm['message']}"
                    if 0 <= diff <= 300 and key not in fired:
                        fired.add(key)
                        self.root.after(0, lambda a=alarm: self._alarm_co(a))
                except Exception: pass

    def _test_alarm(self):
        cfg = load_cfg()
        now_text = datetime.datetime.now().strftime("%H:%M")
        self._alarm_co({"time": now_text, "message": tr("test_alarm_message", cfg)})

    def _alarm_co(self, alarm=None):
        cfg = load_cfg()
        alarm = _normalize_alarm(alarm or _default_alarm(lang_code(cfg)), lang_code(cfg))
        self._force("alarm", 99999)
        def on_done():
            with self._lock: self._forced_state = None; self._force_until = 0.0
        AlarmWindow(self.root, on_done=on_done, alarm=alarm)

    def _settings(self):
        SettingsWindow(self.root, load_cfg())

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
