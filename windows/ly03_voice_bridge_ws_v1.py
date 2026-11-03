"""LY-03 Android touch -> Windows voice-hotkey bridge (experimental).

Requires only Python standard library; no phone app, root, or Windows driver.
This is a separate WebSocket version; v3 HTTP prototype remains unchanged.
Start on Windows (replace the example with your OWN configured voice input hotkey):
    py ly03_voice_bridge_ws_v1.py --hotkey "ctrl+win"
    py ly03_voice_bridge_ws_v1.py --hotkey "win+h"

Single center press: configured shortcut (after ~300 ms).
Rapid double center press: Enter, without sending the single-press shortcut.
Open the printed LAN URL on your Android phone, keep the page foreground and
unlocked, and press LY-03's center button. Ctrl+C stops the server.

SECURITY: Listen only on a trusted private LAN; a random per-run token protects
all actions. Commands are restricted to the configured hotkey, Enter, and optional page
keys. The HTTP LAN traffic is not encrypted. Do not forward the port to the web.
"""
from __future__ import annotations

import argparse
import subprocess
import base64
import hashlib
import re
import struct
import threading
from collections import OrderedDict
import ctypes
import json
import secrets
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from html import escape

TOKEN = secrets.token_urlsafe(20)

# Windows virtual-key codes. Strict allowlist: never accept arbitrary remote keys.
VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "pageup": 0x21, "pagedown": 0x22,
}
for code in range(ord("A"), ord("Z") + 1):
    VK[chr(code).lower()] = code
for code in range(ord("0"), ord("9") + 1):
    VK[chr(code)] = code
for i in range(1, 13):
    VK[f"f{i}"] = 0x6F + i
MODIFIERS = {"ctrl", "shift", "alt", "win"}
EXTENDED_KEYS = {"up", "down", "left", "right", "pageup", "pagedown"}
ALIASES = {
    "control": "ctrl", "ctl": "ctrl", "windows": "win", "super": "win",
    "option": "alt", "return": "enter", "escape": "esc", "pgup": "pageup",
    "pgdn": "pagedown", " ": "space",
}


def parse_hotkey(value: str) -> tuple[str, ...]:
    parts = [ALIASES.get(p.strip().lower(), p.strip().lower()) for p in value.split("+")]
    if not 1 <= len(parts) <= 5 or any(not p or p not in VK for p in parts):
        raise argparse.ArgumentTypeError(
            "Invalid shortcut. Examples: ctrl+alt+space, ctrl+shift+v, win+shift+s, f8"
        )
    if len(set(parts)) != len(parts):
        raise argparse.ArgumentTypeError("Duplicate key in shortcut")
    nonmods = [p for p in parts if p not in MODIFIERS]
    # Most shortcuts have one ordinary key (Win+H). Some input methods use a
    # modifier-only chord, such as Ctrl+Win, so allow 2+ modifiers by themselves.
    if len(nonmods) > 1 or (len(nonmods) == 0 and len(parts) < 2):
        raise argparse.ArgumentTypeError(
            "Specify one non-modifier key, or at least two modifiers (e.g. ctrl+win)"
        )
    return tuple([m for m in ("ctrl", "shift", "alt", "win") if m in parts] + nonmods)


def press_combo(keys: tuple[str, ...]) -> None:
    if sys.platform != "win32":
        print(f"[test/non-Windows] would press {'+'.join(keys)}", flush=True)
        return
    # keybd_event is a Windows compatibility API and works on ordinary desktop
    # apps; it can be blocked by elevated apps or application-specific handlers.
    user32 = ctypes.windll.user32
    held = []
    try:
        for key in keys:
            flags = 0x0001 if key in EXTENDED_KEYS else 0  # KEYEVENTF_EXTENDEDKEY
            user32.keybd_event(VK[key], 0, flags, 0)
            held.append(key)
        # A modifier-only shortcut must have a brief moment when all modifier
        # keys are physically 'down'. This helps apps detect Ctrl+Win chords.
        if all(k in MODIFIERS for k in keys):
            time.sleep(0.12)
    finally:
        for key in reversed(held):
            flags = 0x0002 | (0x0001 if key in EXTENDED_KEYS else 0)
            user32.keybd_event(VK[key], 0, flags, 0)


def local_addresses() -> list[str]:
    result: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                result.add(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))  # No packets are sent.
            result.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(result)


def preferred_phone_address(addresses: list[str]) -> str | None:
    """Prefer phone-reachable LAN ranges, avoiding virtual adapter addresses."""
    preferred = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))  # Select route; no UDP data sent.
            preferred = sock.getsockname()[0]
    except OSError:
        pass
    # Some Windows virtual adapters report 172.18.x.x as the default route;
    # prefer the actual 192.168.x.x LAN when both addresses are present.
    wifi = [ip for ip in addresses if ip.startswith("192.168.")]
    private10 = [ip for ip in addresses if ip.startswith("10.")]
    private172 = [ip for ip in addresses
                  if ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31]
    for pool in (wifi, private10, private172):
        if pool:
            return preferred if preferred in pool else sorted(pool)[0]
    return None


def phone_address_choices(addresses: list[str], show_all: bool = False) -> list[str]:
    """Print one recommended private LAN IP by default, or all detected IPs on demand.

    Interface availability cannot prove a phone can actually reach an address.
    """
    if show_all:
        return sorted(set(addresses))
    recommended = preferred_phone_address(addresses)
    return [recommended] if recommended else []


def copy_url_to_clipboard(url: str) -> bool:
    """Copy the entire ephemeral-token URL to the Windows clipboard."""
    if sys.platform != "win32":
        return False
    try:
        subprocess.run(["clip.exe"], input=url, text=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Open Input Bridge · 输入控制</title>
<style>
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:#101b2c;color:#eff7ff;font:16px system-ui,-apple-system,sans-serif;overscroll-behavior:none}
main{min-height:100dvh;display:flex;flex-direction:column;gap:12px;padding:18px}
h1{font-size:22px;margin:0}p{font-size:13px;line-height:1.5;margin:0;color:#b7cadd}
#pad{flex:1;min-height:190px;display:flex;justify-content:center;align-items:center;text-align:center;
 flex-direction:column;gap:12px;border:2px dashed #628aa8;border-radius:20px;background:#182b42;touch-action:none;user-select:none}
#status{font-size:23px;font-weight:700;color:#79e3bf}#detail{font-size:13px;color:#c2d9ed;padding:0 18px}
#counter{font-size:13px;color:#b3c6da}#log{height:116px;white-space:pre-wrap;overflow:auto;font:12px/1.5 monospace;color:#afc3d6}
.buttons{display:flex;gap:8px}.buttons button{flex:1;padding:13px;border:0;border-radius:11px;background:#2c6087;color:white;font-size:14px;font-weight:700}
#toggle{background:#256b53}.network{border:1px solid #35536b;border-radius:12px;padding:10px;color:#e2eefc;font-size:13px;background:#172638}.network strong{color:#82e8c2}.network .offline{color:#ffce8d}.warn{color:#ffc978}
</style></head><body><main>
<h1>Open Input Bridge → Windows</h1>
<p>中间按钮：<strong>单击 → __HOTKEY_HTML__</strong>，<strong>快速双击 → Enter（发送）</strong>；上下操作：<strong>立即滚动 → __SWIPE_HTML__</strong>（每次 __SCROLL_STEPS__ 步）。请先让电脑网页或目标输入框获得焦点。</p>
<div class="network">连接：<strong id="netstate" class="offline">连接中…</strong>　运行：<span id="uptime">0:00</span>　重连：<span id="retries">0</span> 次　心跳 RTT：<span id="rtt">—</span> ms<br><span id="lastack">等待 WebSocket 连接</span></div>
<div id="pad"><div id="status">等待输入事件…</div><div id="detail">中间键双击判定 __DOUBLE_MS__ms；上下键立即执行，无双击等待</div></div>
<div id="counter">单击：0　双击：0　↑：0　↓：0</div>
<div class="buttons"><button id="manual">测试：单击组合键</button><button id="manualDouble">测试：双击 Enter</button></div>
<div class="buttons"><button id="manualUp">测试：↑ 上移</button><button id="manualDown">测试：↓ 下移</button></div>
<div class="buttons"><button id="toggle">暂停发送</button></div>
<p class="warn">请保持手机亮屏、桥接页面在前台；断线后不会补发。中间键单击延迟 __DOUBLE_MS__ms 用于识别双击；上下操作不等待，默认滚动 __SCROLL_STEPS__ 个方向键步幅。语音仍在识别时按 Enter，可能只会结束语音整理，不会直接发送消息。</p>
<div id="log"></div>
</main><script>
const TOKEN=__TOKEN_JSON__;
const DOUBLE_MS=__DOUBLE_MS__;
const WHEEL_BURST_MS=__WHEEL_BURST_MS__;
const $=id=>document.getElementById(id);
let armed=true, start=null, pstart=null, ignoreClickUntil=0;
let pendingTapTimer=null, pendingTapAt=0;
let lastWheelAt=0, lastWheelDirection=null, lastGestureDirectionAt=0;
const count={tap:0,double:0,up:0,down:0};
function log(s){$('log').textContent=(new Date().toLocaleTimeString()+' '+s+'\n'+$('log').textContent).slice(0,2100);}
function status(title,detail){$('status').textContent=title;$('detail').textContent=detail;}
function isControl(target){return !!(target && target.closest && target.closest('button,input,select,textarea,a'));}
// Transport: no offline queue. No replay after reconnect (especially important for Enter).
let ws=null, retries=0, backoff=1000, reconnectTimer=null, lastPong=0, latestRtt='—';
let connectedAt=0, clientId=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,13), seq=0;
const outstanding=new Map();
function netstate(s, connected){
 $('netstate').textContent=s;$('netstate').className=connected?'':'offline';
}
function wsAddress(){
 return 'ws://'+location.host+'/ws?token='+encodeURIComponent(TOKEN);
}
function connect(){
 if(ws&&(ws.readyState===WebSocket.CONNECTING||ws.readyState===WebSocket.OPEN))return;
 clearTimeout(reconnectTimer);reconnectTimer=null;
 netstate('正在连接',false);
 let sock;
 try{sock=new WebSocket(wsAddress());}catch(err){log('连接失败 '+err.message);planReconnect();return;}
 ws=sock;
 sock.onopen=()=>{
  if(ws!==sock)return;
  connectedAt=Date.now();lastPong=Date.now();backoff=1000;
  netstate('在线',true);log('WebSocket 已连接');
  $('lastack').textContent='通道在线，可按指环测试';
  sendPing(sock);
 };
 sock.onmessage=e=>{
  if(ws!==sock)return;
  let obj;try{obj=JSON.parse(e.data);}catch{return;}
  if(obj.type==='pong'){
    const now=Date.now();lastPong=now;
    if(Number.isFinite(obj.ts))latestRtt=String(Math.max(0,now-obj.ts));
    $('rtt').textContent=latestRtt;
  }else if(obj.type==='ack'){
    const p=outstanding.get(obj.id);if(p)outstanding.delete(obj.id);
    if(obj.ok){
      $('lastack').textContent='已确认：'+(p?p.cmd:obj.cmd)+(obj.skipped?'（未绑定）':'')+' · '+new Date().toLocaleTimeString();
      log('ACK '+(p?p.cmd:obj.cmd));
    }else{
      $('lastack').textContent='指令未执行：'+(obj.error||'未知原因');log('拒绝指令 '+obj.id);
    }
  }
 };
 sock.onerror=()=>{if(ws===sock)log('WebSocket 网络异常');};
 sock.onclose=e=>{
  if(ws!==sock)return;
  ws=null;lastPong=0;connectedAt=0;
  if(outstanding.size){log('断线，'+outstanding.size+' 条未收到确认，绝不自动重放');outstanding.clear();}
  netstate('已断开',false);$('lastack').textContent='离线；本阶段不会缓存按键';
  log('WebSocket 断开 '+e.code);planReconnect();
 };
}
function planReconnect(){
 if(reconnectTimer!==null)return;
 const delay=backoff;
 reconnectTimer=setTimeout(()=>{reconnectTimer=null;retries++;$('retries').textContent=retries;connect();},delay);
 backoff=Math.min(backoff*2,10000);
}
function sendPing(sock){
 if(sock.readyState!==WebSocket.OPEN)return;
 try{sock.send(JSON.stringify({type:'ping',ts:Date.now()}));}catch{sock.close();}
}
setInterval(()=>{
 const sock=ws;
 if(sock&&sock.readyState===WebSocket.OPEN){
  if(lastPong&&Date.now()-lastPong>35000){log('心跳超时，触发重新连接');sock.close();return;}
  sendPing(sock);
 }
 $('uptime').textContent=connectedAt?Math.floor((Date.now()-connectedAt)/60_000)+':'+String(Math.floor((Date.now()-connectedAt)/1000)%60).padStart(2,'0'):'0:00';
 for(const [id,p] of outstanding){if(Date.now()-p.time>60000)outstanding.delete(id);}
},10000);
window.addEventListener('online',()=>{log('手机网络恢复');if(!ws)connect();});
document.addEventListener('visibilitychange',()=>{
 if(document.hidden){cancelPending();return;}
 log('网页回到前台');if(ws&&ws.readyState===WebSocket.OPEN&&Date.now()-lastPong>35000)ws.close();else if(!ws)connect();
});
window.addEventListener('pagehide',()=>cancelPending());
function send(command,source){
 if(document.hidden)return;
 if(!armed){status('已暂停','点击“恢复发送”后才会向电脑发送快捷键');return;}
 if(!ws||ws.readyState!==WebSocket.OPEN){
   status('网络离线','此次按键未发送；不会在重连后补发');log(source+' '+command+' => DROP offline');return;
 }
 count[command]++;$('counter').textContent=`单击：${count.tap}　双击：${count.double}　↑：${count.up}　↓：${count.down}`;
 const labels={tap:'● 单击组合键',double:'●● 双击 Enter',up:'↑ 上移',down:'↓ 下移'};
 const name=labels[command];
 status(name,`来源：${source}；正在向 Windows 发送指令`);
 const id=clientId+':'+(++seq);
 outstanding.set(id,{cmd:command,time:Date.now()});
 try{ws.send(JSON.stringify({type:'action',id:id,cmd:command}));log(source+' => '+command);}
 catch(err){outstanding.delete(id);log('发送失败 '+err.message);status('发送失败','操作已丢弃，请检查连接状态');}
}
connect();
// A single click must wait for the double-click window to close, otherwise a
// double click would incorrectly send the voice hotkey before Enter.
function queueTap(source){
 if(!armed){status('已暂停','不会向 Windows 发送按键');return;}
 const now=performance.now();
 if(pendingTapTimer!==null && now-pendingTapAt<=DOUBLE_MS){
  clearTimeout(pendingTapTimer);pendingTapTimer=null;pendingTapAt=0;
  log('quick double tap detected');send('double',source+' x2');return;
 }
 if(pendingTapTimer!==null){
  clearTimeout(pendingTapTimer);pendingTapTimer=null;pendingTapAt=0;
  send('tap','previous '+source);
 }
 pendingTapAt=now;
 pendingTapTimer=setTimeout(()=>{
  pendingTapTimer=null;pendingTapAt=0;
  send('tap',source);
 },DOUBLE_MS);
 status('检测到第一次点击',`等待 ${DOUBLE_MS}ms 判断是否双击；单击将触发快捷键`);
}
function cancelTap(){
 if(pendingTapTimer!==null)clearTimeout(pendingTapTimer);
 pendingTapTimer=null;pendingTapAt=0;
}
// LY-03 direction control is single-action only: send immediately without
// waiting for an unreliable directional double-press gesture.
function queueDirection(direction,source){
 if(!armed||document.hidden)return;
 log('direction '+direction+' from '+source);
 send(direction,source);
}
function cancelPending(){cancelTap();}
function finish(x0,y0,x1,y1,elapsed,source){
 const dx=x1-x0,dy=y1-y0; log(`${source} dx=${Math.round(dx)} dy=${Math.round(dy)} ms=${Math.round(elapsed)}`);
 // Swipe UP means scroll the PC page DOWN; swipe DOWN means scroll UP.
 if(Math.abs(dy)>=35&&Math.abs(dy)>Math.abs(dx)*1.3){
  const direction=dy<0?'down':'up';
  lastGestureDirectionAt=Date.now();queueDirection(direction,source);return;
 }
 if(Math.abs(dx)<=24&&Math.abs(dy)<=24&&elapsed<1000){queueTap(source);return;}
 status('收到其他移动',`dx=${Math.round(dx)}, dy=${Math.round(dy)}；未触发快捷键`);
}
// Android Chrome emits touchstart/touchend for touch-injection HID devices.
// Ignore corresponding touch-pointer events to prevent duplicate commands.
document.addEventListener('touchstart',e=>{
 if(isControl(e.target))return;const t=e.changedTouches[0];
 if(t)start={x:t.clientX,y:t.clientY,at:performance.now()};
},{passive:true});
document.addEventListener('touchend',e=>{
 if(!start||isControl(e.target))return;const t=e.changedTouches[0];
 if(t)finish(start.x,start.y,t.clientX,t.clientY,performance.now()-start.at,'touch');
 start=null;ignoreClickUntil=Date.now()+450;
},{passive:true});
document.addEventListener('touchcancel',()=>{start=null;},{passive:true});
document.addEventListener('pointerdown',e=>{
 if(e.pointerType==='touch'||isControl(e.target))return;
 pstart={id:e.pointerId,x:e.clientX,y:e.clientY,at:performance.now(),kind:e.pointerType};
});
document.addEventListener('pointerup',e=>{
 if(e.pointerType==='touch'||!pstart||pstart.id!==e.pointerId||isControl(e.target))return;
 finish(pstart.x,pstart.y,e.clientX,e.clientY,performance.now()-pstart.at,'pointer-'+pstart.kind);
 pstart=null;ignoreClickUntil=Date.now()+400;
});
// Accessibility-injected clicks sometimes arrive with no touch/pointer stream.
document.addEventListener('click',e=>{
 if(isControl(e.target)||Date.now()<ignoreClickUntil)return;
 log('click-only event');queueTap('click-only');ignoreClickUntil=Date.now()+120;
});
document.addEventListener('wheel',e=>{
 if(isControl(e.target))return;const dy=e.deltaY;
 if(Math.abs(dy)<=5)return;
 const now=Date.now(), direction=dy<0?'up':'down';
 // One LY-03 wheel gesture can generate a burst of wheel frames; do not count
 // frames within a burst as a double press. Touch/pointer may also emit a wheel.
 const gap=now-lastWheelAt;
 if(gap<WHEEL_BURST_MS && lastWheelDirection===direction){
  lastWheelAt=now; // Keep related wheel frames within a single gesture.
  return;
 }
 lastWheelAt=now;lastWheelDirection=direction;
 if(now-lastGestureDirectionAt<170){log('wheel ignored after touch '+direction);return;}
 log('wheel gesture '+direction+' gap='+Math.round(gap)+'ms');
 queueDirection(direction,'wheel');
},{passive:true});
document.addEventListener('keydown',e=>{
 if(isControl(e.target)||e.repeat)return;
 if(['Enter','Space'].includes(e.code))queueTap('key-'+e.code);
 else if(['PageUp','ArrowUp'].includes(e.code))queueDirection('up','key-'+e.code);
 else if(['PageDown','ArrowDown'].includes(e.code))queueDirection('down','key-'+e.code);
});
$('manual').addEventListener('click',()=>{cancelPending();send('tap','manual');});
$('manualDouble').addEventListener('click',()=>{cancelPending();send('double','manual');});
$('manualUp').addEventListener('click',()=>{cancelPending();send('up','manual');});
$('manualDown').addEventListener('click',()=>{cancelPending();send('down','manual');});
$('toggle').addEventListener('click',()=>{
 armed=!armed;cancelPending();$('toggle').textContent=armed?'暂停发送':'恢复发送';
 status(armed?'已恢复':'已暂停',armed?'按中间按钮开始测试':'不会向 Windows 发送按键');
});
</script></body></html>'''


# This server uses only Python standard library for a narrow, controlled subset of RFC 6455.
# No WebSocket extensions, fragmentation, arbitrary commands, or offline replay.
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
ID_PATTERN = re.compile(r'^[A-Za-z0-9:-]{1,100}$')
seen = OrderedDict()
seen_lock = threading.Lock()
keyboard_lock = threading.Lock()


def recv_exact(rfile, amount: int) -> bytes:
    b = rfile.read(amount)
    if b is None or len(b) != amount:
        raise EOFError('Closed during websocket frame')
    return b


def recv_frame(rfile) -> tuple[int, bytes]:
    head = recv_exact(rfile, 2)
    b1, b2 = head
    if (b1 & 0x70) or not (b1 & 0x80):
        raise ValueError('Unsupported WebSocket frame format')
    opcode = b1 & 0x0F
    if not (b2 & 0x80):
        raise ValueError('Unmasked client frame')
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack('!H', recv_exact(rfile, 2))[0]
    elif length == 127:
        length = struct.unpack('!Q', recv_exact(rfile, 8))[0]
    if length > 2048:
        raise ValueError('Frame too large')
    if opcode >= 0x8 and length > 125:
        raise ValueError('Control frame too large')
    mask = recv_exact(rfile, 4)
    payload = recv_exact(rfile, length)
    return opcode, bytes(c ^ mask[i & 3] for i, c in enumerate(payload))


def send_frame(wfile, opcode: int, payload: bytes) -> None:
    if len(payload) <= 125:
        frame = bytes([0x80 | opcode, len(payload)])
    else:
        frame = bytes([0x80 | opcode, 126]) + struct.pack('!H', len(payload))
    wfile.write(frame + payload)
    wfile.flush()


def send_json(wfile, obj: dict) -> None:
    send_frame(wfile, 0x1, json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))


def keys_for_action(cmd: str, hotkey: tuple[str, ...], swipes: str) -> tuple[str, ...]:
    """Resolve the wire protocol commands to a fixed Windows key allowlist."""
    if cmd == 'tap':
        return hotkey
    if cmd == 'double':
        return ('enter',)
    if cmd in ('up', 'down', 'up_double', 'down_double'):
        mapping = {'arrows': {'up': 'up', 'down': 'down',
                              'up_double': 'pageup', 'down_double': 'pagedown'},
                   'pages': {'up': 'pageup', 'down': 'pagedown',
                             'up_double': 'pageup', 'down_double': 'pagedown'},
                   'ignore': {}}
        if swipes not in mapping:
            raise ValueError('Invalid swipe mode')
        key = mapping[swipes].get(cmd)
        return (key,) if key else ()
    raise ValueError('Unknown command')


def scroll_repeat_count(cmd: str, swipes: str, steps: int) -> int:
    """Only ordinary single-arrow navigation gets increased travel."""
    return steps if cmd in ('up', 'down') and swipes == 'arrows' else 1


def execute_action(cmd: str, hotkey: tuple[str, ...], swipes: str,
                   scroll_steps: int, dry_run: bool) -> tuple[bool, str]:
    keys = keys_for_action(cmd, hotkey, swipes)
    repetitions = scroll_repeat_count(cmd, swipes, scroll_steps)
    if keys and not dry_run:
        for i in range(repetitions):
            press_combo(keys)
            if i + 1 < repetitions:
                time.sleep(0.018)  # Let foreground apps observe separate arrow presses.
    target = '+'.join(keys) if keys else 'none'
    if keys and repetitions > 1:
        target += f' x{repetitions}'
    return not bool(keys), target


def main() -> None:
    parser = argparse.ArgumentParser(description='Open Input Bridge WebSocket receiver (stdlib only)')
    parser.add_argument('--hotkey', type=parse_hotkey, default=parse_hotkey('ctrl+win'),
                        help='Voice input shortcut, e.g. ctrl+win (default: Ctrl+Win)')
    parser.add_argument('--double-ms', type=int, default=300,
                        help='Center button double-click threshold (default 300ms)')
    parser.add_argument('--wheel-burst-ms', type=int, default=75,
                        help='Treat consecutive wheel frames as one event under this gap (default 75ms)')
    parser.add_argument('--scroll-steps', type=int, default=8,
                        help='Arrow key presses for a single up/down action (default 8)')
    parser.add_argument('--swipes', choices=('arrows', 'pages', 'ignore'), default='arrows',
                        help='Map LY-03 up/down events to ArrowUp/ArrowDown (default), PageUp/PageDown, or ignore')
    parser.add_argument('--port', type=int, default=8766, help='Default 8766, does not collide with HTTP v3 port 8765')
    parser.add_argument('--dry-run', action='store_true', help='Log actions without injecting keyboard input')
    parser.add_argument('--copy-url', action='store_true', help='Copy a LAN URL with this run token to Windows clipboard')
    parser.add_argument('--show-all-addresses', action='store_true',
                        help='List all detected interface IPs (including virtual adapters) for troubleshooting')
    parser.add_argument('--bind', default='0.0.0.0', help='Use 127.0.0.1 for safe local test')
    args = parser.parse_args()
    if not 180 <= args.double_ms <= 600:
        parser.error('--double-ms must be between 180 and 600')
    if not 30 <= args.wheel_burst_ms <= 180:
        parser.error('--wheel-burst-ms must be between 30 and 180')
    if not 1 <= args.scroll_steps <= 16:
        parser.error('--scroll-steps must be between 1 and 16')
    if not 1 <= args.port <= 65535:
        parser.error('--port must be 1..65535')

    def execute(cmd):
        skipped, target = execute_action(cmd, args.hotkey, args.swipes,
                                         args.scroll_steps, args.dry_run)
        result = 'IGNORED' if skipped else 'DRY-RUN' if args.dry_run else 'SENT'
        print(f'[BRIDGE] {cmd} -> {target} ({result})', flush=True)
        return skipped

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def handle_one_request(self):
            try:
                super().handle_one_request()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                # Android/browser clients can close an HTTP socket while the
                # server is waiting for a request (or writing a response).
                # This is not a failed keyboard action or a server crash.
                self.close_connection = True

        def respond(self,status:int,data:bytes,mime='text/plain; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            # The page is served once; only the upgraded /ws channel is long-lived.
            # Avoid leaving idle HTTP keep-alive threads waiting for a phone reset.
            self.send_header('Connection','close')
            self.close_connection = True
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path=urlsplit(self.path)
            supplied=parse_qs(path.query).get('token',[''])[0]
            if not secrets.compare_digest(supplied,TOKEN):
                self.respond(403,b'Forbidden');return
            if path.path=='/':
                page=(PAGE.replace('__TOKEN_JSON__',json.dumps(TOKEN))
                      .replace('__HOTKEY_HTML__',escape('+'.join(args.hotkey).upper()))
                      .replace('__SWIPE_HTML__',{'arrows':'↑/↓ 方向键', 'pages':'PageUp/PageDown', 'ignore':'忽略'}[args.swipes])
                      .replace('__DOUBLE_MS__',str(args.double_ms))
                      .replace('__WHEEL_BURST_MS__',str(args.wheel_burst_ms))
                      .replace('__SCROLL_STEPS__',str(args.scroll_steps)))
                self.respond(200,page.encode('utf-8'),'text/html; charset=utf-8')
            elif path.path=='/ws':
                self.ws_session()
            else:self.respond(404,b'Not Found')

        def ws_session(self):
            origin=self.headers.get('Origin','')
            if origin != 'http://'+self.headers.get('Host',''):
                self.respond(403,b'Unexpected Origin');return
            key=self.headers.get('Sec-WebSocket-Key','')
            try:
                valid=(len(base64.b64decode(key,validate=True))==16)
            except (ValueError,base64.binascii.Error):valid=False
            if (not valid or self.headers.get('Sec-WebSocket-Version')!='13'
                or self.headers.get('Upgrade','').lower()!='websocket'
                or 'upgrade' not in self.headers.get('Connection','').lower()):
                self.respond(400,b'Invalid websocket handshake');return
            accept=base64.b64encode(hashlib.sha1((key+WS_GUID).encode('ascii')).digest()).decode('ascii')
            self.send_response(101,'Switching Protocols')
            self.send_header('Upgrade','websocket')
            self.send_header('Connection','Upgrade')
            self.send_header('Sec-WebSocket-Accept',accept)
            self.end_headers()
            self.wfile.flush()
            self.close_connection=True
            self.connection.settimeout(45)  # Client heartbeat at 10s; stale sessions released.
            print('[WS] connected',self.client_address[0],flush=True)
            try:
                while True:
                    opcode,payload=recv_frame(self.rfile)
                    if opcode==0x8:break
                    if opcode==0x9:
                        send_frame(self.wfile,0xA,payload);continue
                    if opcode==0xA:continue
                    if opcode!=0x1:raise ValueError('Only UTF-8 JSON text supported')
                    data=json.loads(payload.decode('utf-8'))
                    if not isinstance(data,dict):raise ValueError('Invalid object')
                    typ=data.get('type')
                    if typ=='ping':
                        ts=data.get('ts')
                        if not isinstance(ts,(float,int)):ts=0
                        send_json(self.wfile,{'type':'pong','ts':ts})
                    elif typ=='action':
                        id=data.get('id');cmd=data.get('cmd')
                        if not isinstance(id,str) or not ID_PATTERN.fullmatch(id) or cmd not in ('tap','double','up','down','up_double','down_double'):
                            send_json(self.wfile,{'type':'ack','id':id if isinstance(id,str) else None,'ok':False,'error':'Invalid action'});continue
                        with seen_lock:
                            was_seen=id in seen
                            if not was_seen:
                                seen[id]=True
                                if len(seen)>4096:seen.popitem(last=False)
                        if was_seen:
                            print('[WS] dropped duplicate action id',flush=True)
                            send_json(self.wfile,{'type':'ack','id':id,'cmd':cmd,'ok':True,'duplicate':True});continue
                        try:
                            with keyboard_lock:skipped=execute(cmd)
                            send_json(self.wfile,{'type':'ack','id':id,'cmd':cmd,'ok':True,'skipped':skipped})
                        except Exception as exc:
                            print('[WS] error executing action',type(exc).__name__,flush=True)
                            send_json(self.wfile,{'type':'ack','id':id,'cmd':cmd,'ok':False,'error':'Command failed'})
                    else:raise ValueError('Unsupported message')
            except (EOFError,ConnectionError,TimeoutError,OSError):
                pass
            except (ValueError,UnicodeDecodeError,json.JSONDecodeError) as exc:
                print('[WS] protocol error:',str(exc)[:90],flush=True)
            finally:
                print('[WS] disconnected',self.client_address[0],flush=True)

        def log_message(self,fmt,*values):
            if self.path.startswith('/ws'):return # Never log access tokens.
            if self.command!='GET':super().log_message(fmt,*values)

    print('\nOpen Input Bridge | '+('DRY RUN' if args.dry_run else 'LIVE INPUT'))
    print('Tap: '+('+'.join(args.hotkey))+'; double: Enter; window '+str(args.double_ms)+'ms')
    print('Up/Down single: '+{'arrows':f'ArrowUp / ArrowDown x{args.scroll_steps}', 'pages':'PageUp / PageDown', 'ignore':'disabled'}[args.swipes])
    print('Up/Down: immediate single-direction commands; wheel gap '+str(args.wheel_burst_ms)+'ms')
    print('No offline command queue. 10s heartbeat; 35s stale check; 1s->10s auto-reconnect.')
    print('First phase: phone display ON, test page foreground, trusted private Wi-Fi.')
    try:server=ThreadingHTTPServer((args.bind,args.port),Handler)
    except OSError as exc:parser.exit(1,f'Cannot start websocket bridge: {exc}\n')
    addresses = local_addresses() if args.bind == '0.0.0.0' else []
    displayed = phone_address_choices(addresses, args.show_all_addresses)
    if displayed:
        for addr in displayed:
            print(f'Open on PHONE: http://{addr}:{args.port}/?token={TOKEN}')
        if not args.show_all_addresses and len(set(addresses)) > 1:
            print('[NETWORK] Showing recommended private LAN address only; '
                  'use --show-all-addresses to inspect other detected interfaces.')
    elif args.bind != '0.0.0.0':
        print(f'Open locally: http://{args.bind}:{args.port}/?token={TOKEN}')
    else:
        print('[NETWORK] No recommended private LAN IPv4 found; '
              'use --show-all-addresses to inspect detected interface addresses.')
        if args.show_all_addresses:
            print('[NETWORK] No interface IPv4 addresses detected.')
    if args.copy_url:
        phone_ip = preferred_phone_address(addresses)
        if phone_ip:
            url = f'http://{phone_ip}:{args.port}/?token={TOKEN}'
            if copy_url_to_clipboard(url):
                print(f'[CLIPBOARD] Phone URL copied: http://{phone_ip}:{args.port}/?token=[hidden]')
            else:
                print('[CLIPBOARD] Could not copy phone URL; copy the printed link manually.')
        else:
            print('[CLIPBOARD] No recommended private LAN address; inspect --show-all-addresses and copy an appropriate URL manually.')
    print('Only allow Python on PRIVATE networks; never expose this port to the internet.')
    print('Press Ctrl+C to stop.\n',flush=True)
    try:server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()
    print('Stopped')


if __name__=='__main__':
    main()