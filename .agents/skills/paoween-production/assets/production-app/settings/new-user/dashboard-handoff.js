(() => {
  const key = 'paoween-onboarding-handoff';
  const raw = sessionStorage.getItem(key);
  sessionStorage.removeItem(key);
  if (!raw) return;

  let state;
  try { state = JSON.parse(raw); } catch { return; }
  const salary = Number(state.salary);
  const hasSalary = Number.isFinite(salary) && salary > 0;
  const english = localStorage.getItem('paoween-language') === 'en' || document.documentElement.lang.toLowerCase().startsWith('en');
  const box = document.createElement('aside');
  box.className = 'onboarding-handoff';
  box.setAttribute('role', 'status');
  const heading = document.createElement('strong');
  heading.textContent = english ? 'You’re all set to begin' : 'เริ่มต้นกับเป๋าวีนแล้ว';
  const detail = document.createElement('p');
  detail.textContent = hasSalary
    ? (english ? `Take-home salary shared: ฿${salary.toLocaleString('en-US')} / month · temporary preview only`
      : `เงินเดือนสุทธิที่แจ้งไว้ ฿${salary.toLocaleString('th-TH')} / เดือน · ใช้ในตัวอย่างนี้ชั่วคราว`)
    : (english ? 'You can add your monthly take-home salary later.' : 'เพิ่มเงินเดือนสุทธิภายหลังได้');
  const slip = document.createElement('p');
  const setSlipMessage = attached => {
    slip.textContent = attached
      ? (english ? 'The slip is ready in the attachment tray. Review it and press Send when ready; it has not been processed or saved.' : 'ภาพสลิปพร้อมอยู่ในช่องแนบ ตรวจดูก่อนกดส่งได้เลย ตอนนี้ยังไม่ได้อ่านหรือบันทึก')
      : (english ? 'Start adding expense slips from today when you’re ready.' : 'พร้อมเมื่อไหร่ ส่งสลิปรายจ่ายตั้งแต่วันนี้ได้เลย');
  };
  box.append(heading, detail, slip);
  document.querySelector('main')?.prepend(box);

  let appReady = false;
  let pendingFile = null;
  const queueFile = file => {
    if (!appReady) { pendingFile = file; return; }
    try {
      const input = document.getElementById('receipt-file');
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      pendingFile = null;
    } catch {
      setSlipMessage(false);
    }
  };
  window.addEventListener('paoween-ui-ready', () => {
    appReady = true;
    if (pendingFile) queueFile(pendingFile);
  }, { once: true });

  const takeStagedSlip = () => new Promise((resolve, reject) => {
    const request = indexedDB.open('paoween-production-handoff-v1', 1);
    request.onupgradeneeded = () => { if (!request.result.objectStoreNames.contains('handoff')) request.result.createObjectStore('handoff'); };
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('handoff', 'readwrite');
      const store = tx.objectStore('handoff');
      let value = null;
      const get = store.get('slip');
      get.onsuccess = () => { value = get.result || null; };
      store.delete('slip');
      tx.oncomplete = () => { db.close(); resolve(value); };
      tx.onerror = tx.onabort = () => { db.close(); reject(tx.error || new Error('IndexedDB read failed')); };
    };
  });

  takeStagedSlip().then(staged => {
    if (!state.hasSlip || !staged || !staged.blob) { setSlipMessage(false); return; }
    try {
      const file = new File([staged.blob], staged.name || 'expense-slip', { type: staged.type || staged.blob.type || 'image/jpeg' });
      setSlipMessage(true);
      queueFile(file);
    } catch {
      setSlipMessage(false);
    }
  }).catch(() => setSlipMessage(false));
})();
