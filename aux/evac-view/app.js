'use strict';
const $ = id => document.getElementById(id);
const phases = {waiting:'В очереди', downloading:'Загрузка', ready:'Подготовлен', uploading:'Передача', paused:'Пауза', complete:'Готово'};
let current = null, selected = null, failed = false;
const number = (n, digits=0) => new Intl.NumberFormat('ru-RU', {maximumFractionDigits:digits}).format(n);
function bytes(n) {
  if (n == null) return '—';
  const units = ['B','KiB','MiB','GiB','TiB'];
  let i = 0;
  while (n >= 1024 && i < units.length-1) { n /= 1024; i++; }
  return number(n, i > 1 ? 1 : 0) + ' ' + units[i];
}
function element(tag, cls, text) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text != null) el.textContent = text;
  return el;
}
function health() {
  const age = current ? Math.max(0, Date.now()/1000-current.generated_at) : Infinity;
  const stale = failed || age > 30;
  let text = 'Обновляем состояние', cls = 'muted';
  if (current) {
    if (stale) { text = 'Нет свежих данных'; cls = 'warn'; }
    else if (current.warnings.length) { text = 'Требует внимания'; cls = 'warn'; }
    else if (current.summary.completed === current.summary.total) { text = 'Доставка завершена'; cls = ''; }
    else if (current.running) { text = 'Доставка идёт'; cls = ''; }
  }
  $('health').textContent = text;
  $('health').className = 'badge ' + cls;
  $('updated').textContent = current ? 'Обновлено ' + (age < 2 ? 'только что' : number(age) + ' с назад') : 'Получаем состояние';
  if (stale) { $('speed').textContent = '—'; $('speed-note').textContent = 'Ожидаем свежий замер'; }
  const warnings = current ? [...current.warnings] : [];
  if (stale && (current || failed)) warnings.unshift('Состояние страницы не обновляется. Показаны последние полученные данные.');
  $('warnings').replaceChildren(...warnings.map(w => element('div','',w)));
  $('warnings').hidden = !warnings.length;
}
function chart(data) {
  const end = data.generated_at, start = end - 900;
  const points = data.history.filter(p => p.at >= start && p.mbps != null);
  const max = Math.max(1000, ...points.map(p => p.mbps)) * 1.08;
  $('chart-scale').textContent = '0–' + number(max) + ' Мбит/с';
  // Break the line where the collector had no trustworthy measurement.
  let line = '', area = '', segment = [];
  const flush = () => {
    if (segment.length > 1) {
      const d = segment.map((p,i) => (i ? 'L' : 'M') + p.join(',')).join(' ');
      line += d + ' ';
      area += 'M' + segment[0][0] + ',125 ' + segment.map(p=>'L'+p.join(',')).join(' ') + ' L'+segment[segment.length-1][0]+',125 Z ';
    }
    segment = [];
  };
  for (const p of data.history) {
    if (p.at < start) continue;
    if (p.mbps == null) { flush(); continue; }
    segment.push([((p.at-start)/900*800).toFixed(2), (125-p.mbps/max*115).toFixed(2)]);
  }
  flush();
  $('chart-line').setAttribute('d',line);
  $('chart-area').setAttribute('d',area);
}
function detail() {
  const shard = current && current.shards.find(s=>s.id===selected);
  if (!shard) return;
  const title = element('div','detail-title');
  title.append(element('strong','',`Шард ${shard.id}`), element('span','',phases[shard.phase]),
    element('span','subtle',shard.volume || 'Раздел ещё не выбран'), element('span','subtle',bytes(shard.bytes)));
  const content = [title];
  if (shard.archive) content.push(element('div','detail-file',shard.archive + (shard.phase === 'complete' ? '' : '.partial')));
  if (shard.sha256) content.push(element('div','detail-hash','SHA-256 при передаче · '+shard.sha256));
  if (shard.phase==='uploading' && shard.mbps != null) content.push(element('div','subtle',number(shard.mbps,1)+' Мбит/с · '+(shard.compression || 'tar')));
  $('detail').replaceChildren(...content);
}
function render(data) {
  current = data;
  $('completed').textContent = data.summary.completed;
  $('total').textContent = data.summary.total;
  $('received').textContent = bytes(data.summary.bytes);
  $('speed').textContent = data.summary.mbps == null ? '—' : number(data.summary.mbps);
  $('speed-note').textContent = data.summary.mbps == null ? 'Собираем первый замер' :
    'средняя за ' + number(data.summary.window_seconds || 40) + ' с';
  $('active').textContent = data.summary.active;
  $('overall').max = data.summary.total;
  $('overall').value = data.summary.completed;
  $('percent').textContent = number(data.summary.completed/data.summary.total*100) + '% шардов';
  $('connection').textContent = data.connected ? 'На связи' : 'Нет связи';
  $('service').textContent = data.running ? 'Работает' : (data.service.SubState==='exited' && data.summary.completed===data.summary.total ? 'Завершён' : 'Неактивен');
  $('restarts').textContent = data.service.NRestarts == null ? '—' : data.service.NRestarts;
  $('source-free').textContent = data.source.available ? bytes(data.source.free_bytes) : 'Нет свежих данных';
  $('volumes').replaceChildren(...data.volumes.map(v => {
    const card = element('article','volume'), title = element('div','volume-title');
    const active = data.shards.filter(s=>s.volume===v.name && s.phase==='uploading');
    title.append(element('strong','',v.name),element('span','',active.map(s=>'#'+s.id).join(', ') || (v.available ? 'Ожидание' : 'Недоступен')));
    const bar = element('progress');
    bar.max = v.total_bytes || 1; bar.value = v.available ? v.total_bytes-v.free_bytes : 0;
    bar.setAttribute('aria-label',v.name+': занятое место');
    const caption = element('div','volume-caption');
    caption.append(element('span','',v.available ? bytes(v.free_bytes)+' свободно' : 'Нет данных'),element('span','',v.available ? '/ '+bytes(v.total_bytes) : ''));
    card.append(title,bar,caption); return card;
  }));
  // Keep the buttons in place so keyboard focus survives periodic updates.
  for (const shard of data.shards) {
    let button = $('shard-'+shard.id);
    if (!button) {
      button = element('button','shard'); button.id='shard-'+shard.id; button.type='button';
      const title = element('strong','',shard.id); title.append(element('i'));
      button.append(title,element('span'));
      button.addEventListener('click',()=>{
        selected=shard.id;
        for (const b of $('shards').children) b.setAttribute('aria-pressed',String(b===button));
        detail();
      });
      $('shards').append(button);
    }
    button.className='shard '+shard.phase;
    button.setAttribute('aria-pressed',String(selected===shard.id));
    button.setAttribute('aria-label',`Шард ${shard.id}: ${phases[shard.phase]}, ${bytes(shard.bytes)}`);
    button.lastElementChild.textContent=shard.bytes ? bytes(shard.bytes) : phases[shard.phase];
    button.title=[phases[shard.phase],shard.volume,bytes(shard.bytes)].filter(Boolean).join(' · ');
  }
  chart(data); detail(); health();
}
async function refresh() {
  const controller = new AbortController();
  const timeout = setTimeout(()=>controller.abort(),12000);
  try {
    const response=await fetch('/api/status',{cache:'no-store',signal:controller.signal});
    if (!response.ok) throw new Error('Status '+response.status);
    const data=await response.json();
    failed=false; render(data);
  } catch (_) { failed=true; health(); }
  finally { clearTimeout(timeout); }
  setTimeout(refresh,5000);
}
setInterval(health,1000);
refresh();
