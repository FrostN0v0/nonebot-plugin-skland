const prefix = '/maa/bind';
const entry = new URL(location.href).searchParams.get('request');
const form = document.getElementById('form');
const button = document.getElementById('submit');
const error = document.getElementById('error');
const redeem = document.getElementById('redeem');
const deadline = Date.now() + 600000;
const labels = {
  pending: '等待 QQ 发起者核对网页校验码并确认。', approved: '已确认，请领取连接设置。',
  delivered: '连接设置已领取。若设置丢失，请重新 /MAA绑定。',
  cancelled: '本次绑定已取消。', superseded: '本次确认对应其他浏览器，请重新申请。', ended: '本次绑定已结束。'
};
let timer, ended = false, delay = 4000, polling = false;
function show(data) {
  if (data.code) {
    document.getElementById('result').hidden = false;
    document.getElementById('code').textContent = data.code;
    document.getElementById('device').value = data.device;
    document.getElementById('device').disabled = true;
    button.disabled = true;
    document.getElementById('status').textContent = labels[data.state] || '处理中';
  }
  redeem.hidden = data.state !== 'approved';
  ended = !['pending', 'not_submitted'].includes(data.state);
}
function schedule() {
  clearTimeout(timer);
  if (!ended && !document.hidden && Date.now() < deadline) timer = setTimeout(poll, delay);
}
async function poll() {
  if (polling || ended) return;
  if (Date.now() >= deadline) { error.textContent = '链接已过期，请重新 /MAA绑定。'; button.disabled = true; return; }
  polling = true;
  try {
    const response = await fetch(`${prefix}/api/status?entry=${encodeURIComponent(entry)}`, {cache:'no-store', signal:AbortSignal.timeout(8000)});
    const data = await response.json();
    if (!response.ok) { error.textContent = data.error || '链接已失效'; ended = true; button.disabled = true; return; }
    delay = 4000; error.textContent = ''; show(data);
  } catch (_) { delay = Math.min(delay * 2, 30000); error.textContent = '连接暂不可用，正在间隔重试。'; }
  finally { polling = false; schedule(); }
}
form.addEventListener('submit', async event => {
  event.preventDefault(); error.textContent = ''; button.disabled = true;
  try {
    const response = await fetch(`${prefix}/api/submit`, {method:'POST', headers:{'Content-Type':'application/json'},
      signal:AbortSignal.timeout(8000), body:JSON.stringify({request:entry,device:document.getElementById('device').value})});
    const data = await response.json();
    if (!response.ok) { error.textContent = data.error || '提交失败'; button.disabled = false; return; }
    show(data); schedule();
  } catch (_) { error.textContent = '提交结果未知，请在当前浏览器重试。'; button.disabled = false; }
});
redeem.addEventListener('click', async () => {
  redeem.disabled = true;
  try {
    const response = await fetch(`${prefix}/api/redeem?entry=${encodeURIComponent(entry)}`, {method:'POST', signal:AbortSignal.timeout(8000)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '领取失败');
    document.getElementById('settings').hidden = false;
    document.getElementById('task').value = data.get_task;
    document.getElementById('report').value = data.report_status;
    document.getElementById('key').value = data.key;
    redeem.hidden = true; error.textContent = '';
  } catch (_) { error.textContent = '连接设置未能领取。为保护密钥，请重新 /MAA绑定 后申请。'; }
});
document.addEventListener('visibilitychange', () => { clearTimeout(timer); if (!document.hidden) poll(); });
if (!entry) { error.textContent = '请在 QQ 私聊或群聊发送 /MAA绑定，使用机器人返回的链接。'; button.disabled = true; }
else { poll(); }
