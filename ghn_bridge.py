import os
import tarfile
import threading
import queue
import asyncio
import time
import concurrent.futures
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_TAR = os.path.join(BASE_DIR, "ghn_profile_mini.tar.gz")
EXTRACT_DIR = os.path.join(BASE_DIR, ".ghn_profile")

class GHNSyncClient:
    def __init__(self):
        self._ensure_profile()
        self.req_queue = queue.Queue()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.ready_evt = threading.Event()
        self.init_error = None
        self.thread.start()
        self.ready_evt.wait(timeout=30)
        if self.init_error:
            raise RuntimeError(f"GHN Client Init Failed: {self.init_error}")

    def _ensure_profile(self):
        if not os.path.exists(EXTRACT_DIR):
            if os.path.exists(PROFILE_TAR):
                os.makedirs(EXTRACT_DIR, exist_ok=True)
                with tarfile.open(PROFILE_TAR, "r:gz") as tar:
                    tar.extractall(EXTRACT_DIR)
            else:
                raise FileNotFoundError(f"Missing {PROFILE_TAR}")

    def _run_loop(self):
        asyncio.run(self._async_worker())

    async def _async_worker(self):
        try:
            pw = await async_playwright().start()
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=EXTRACT_DIR,
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://nhanh.ghn.vn/lastmile/trip-list", wait_until="networkidle")
            self.ready_evt.set()
        except Exception as e:
            self.init_error = e
            self.ready_evt.set()
            return

        js = """async ({ path, payload, warehouseId }) => {
            const token = localStorage.getItem('SESSION');
            const kp = await new Promise((res, rej) => {
                const req = indexedDB.open('lm-reqsig');
                req.onsuccess = () => {
                    const tx = req.result.transaction('k', 'readonly');
                    const r = tx.objectStore('k').get('kp');
                    r.onsuccess = () => res(r.result);
                    r.onerror = rej;
                };
                req.onerror = rej;
            });
            const toBase64Url = (buf) => {
                let bin = '';
                const bytes = new Uint8Array(buf);
                for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
                return btoa(bin).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
            };
            const bodyStr = typeof payload === 'string' ? payload : JSON.stringify(payload);
            const bodyHashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(bodyStr));
            const bodyHash = toBase64Url(bodyHashBuf);
            const ts = Date.now().toString();
            const nonceBytes = new Uint8Array(16);
            crypto.getRandomValues(nonceBytes);
            const nonce = toBase64Url(nonceBytes);
            const strToSign = ['v1', ts, nonce, 'POST', path, bodyHash].join('\\n');
            const sigBuf = await crypto.subtle.sign({ name: 'ECDSA', hash: { name: 'SHA-256' } }, kp.privateKey, new TextEncoder().encode(strToSign));
            let binSig = '';
            const sigBytes = new Uint8Array(sigBuf);
            for (let i = 0; i < sigBytes.byteLength; i++) binSig += String.fromCharCode(sigBytes[i]);
            const sig = btoa(binSig);
            
            const headers = {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json',
                'X-WarehouseId': warehouseId || localStorage.getItem('CURRENT_HUB') || '1045',
                'X-Sig-TS': ts,
                'X-Sig-Nonce': nonce,
                'X-Sig-Body': bodyHash,
                'X-Sig': sig
            };
            
            const res = await fetch('https://nhanh-api.ghn.vn' + path, {
                method: 'POST',
                headers: headers,
                body: bodyStr
            });
            return await res.json();
        }"""

        while True:
            item = self.req_queue.get()
            if item is None:
                break
            url, payload, warehouse_id, fut = item
            try:
                path = url.replace("https://nhanh-api.ghn.vn", "")
                res = await page.evaluate(js, {
                    'path': path,
                    'payload': payload,
                    'warehouseId': str(warehouse_id) if warehouse_id else None
                })
                fut.set_result(res)
            except Exception as e:
                fut.set_exception(e)

        await ctx.close()
        await pw.stop()

    def post(self, url, payload, warehouse_id=None, timeout=15):
        fut = concurrent.futures.Future()
        self.req_queue.put((url, payload, warehouse_id, fut))
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError("GHN Request Timeout")

    def close(self):
        self.req_queue.put(None)

_client_instance = None
_client_lock = threading.Lock()

def get_ghn_client():
    global _client_instance
    with _client_lock:
        if _client_instance is None:
            _client_instance = GHNSyncClient()
        return _client_instance

if __name__ == "__main__":
    client = get_ghn_client()
    res = client.post("https://nhanh-api.ghn.vn/api/lastmile/trip/get-trip-list-by-hub", {
        "hub_id": "21088000",
        "status": "FINISHED",
        "is_ready": 0,
        "offset": 0,
        "limit": 3,
        "reverse": 1
    }, warehouse_id="21088000")
    print("Test sync post:", res.get("code"), len(res.get("data") or []))
    client.close()
