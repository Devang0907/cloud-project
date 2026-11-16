const currencySelect = document.querySelector('#currency');
const rateInput = document.querySelector('#exchangeRate');
const planningRates = {USD: 1, INR: 85, EUR: 0.9, GBP: 0.8};
let currentResults;
let fullAmount, compactAmount;
function updateCurrency() {
  const currency = currencySelect.value;
  const locale = currency === 'INR' ? 'en-IN' : 'en-US';
  const options = {style: 'currency', currency};
  fullAmount = new Intl.NumberFormat(locale, options);
  compactAmount = new Intl.NumberFormat(locale, {...options, notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 1});
  rateInput.value = planningRates[currency];
  document.querySelector('#rateUnit').textContent = currency;
  document.querySelector('#rateControl').hidden = currency === 'USD';
  if (currentResults) render(currentResults);
}
currencySelect.addEventListener('change', updateCurrency);
rateInput.addEventListener('change', () => {
  const rate = rateInput.valueAsNumber;
  if (Number.isFinite(rate) && rate > 0) planningRates[currencySelect.value] = rate;
  updateCurrency();
});
updateCurrency();
const money = n => fullAmount.format(n * planningRates[currencySelect.value]);
const axisMoney = n => compactAmount.format(n * planningRates[currencySelect.value]);
const form = document.querySelector('#inputs');
let defaults;

function setInputs(values) {
  for (const [key, value] of Object.entries(values)) {
    if (form.elements[key]) form.elements[key].value = value;
  }
}
function getInputs() {
  return Object.fromEntries([...form.querySelectorAll('input')].map(el => [el.name, Number(el.value)]));
}
function rows(parts, total) {
  return Object.entries(parts).map(([name, value]) => `<div class="row"><span>${name}</span><strong>${money(value)}</strong></div>`).join('') + `<div class="row total"><span>Total</span><strong>${money(total)}</strong></div>`;
}
function draw(data) {
  const svg = document.querySelector('#chart');
  const W=900,H=380,L=68,R=16,T=17,B=45, maxMonth=data.month_axis.length-1;
  const maxCost=Math.max(...Object.values(data.curves).map(v=>v.at(-1)))*1.06;
  const x=m=>L+(W-L-R)*m/maxMonth, y=n=>H-B-(H-T-B)*n/maxCost;
  const grid=[0,.25,.5,.75,1].map(f=>`<line x1="${L}" x2="${W-R}" y1="${y(maxCost*f)}" y2="${y(maxCost*f)}" stroke="#dce7da"/><text x="${L-9}" y="${y(maxCost*f)+4}" text-anchor="end" font-size="12" fill="#688074">${axisMoney(maxCost*f)}</text>`).join('');
  const ticks=[0,.25,.5,.75,1].map(f=>`<text x="${x(maxMonth*f)}" y="${H-14}" text-anchor="middle" font-size="12" fill="#688074">${Math.round(maxMonth*f)} mo</text>`).join('');
  const colors={AWS:'#bb641e',GCP:'#09847f','On premises':'#183f69'};
  const lines=Object.entries(data.curves).map(([name,values])=>`<polyline fill="none" stroke="${colors[name]}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" points="${values.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}"/>`).join('');
  const comparison=data.cloud_month.GCP <= data.cloud_month.AWS ? 'GCP' : 'AWS';
  const crossover=data.breakeven_month[comparison];
  const marker=crossover ? `<line x1="${x(crossover)}" x2="${x(crossover)}" y1="${T}" y2="${H-B}" stroke="#197fc0" stroke-width="1.3" stroke-dasharray="5 5"/><text x="${x(crossover)+7}" y="${T+12}" fill="#126da9" font-size="12" font-weight="700">MONTH ${crossover}</text>` : '';
  svg.innerHTML=grid+ticks+marker+lines;
  const series = Object.entries(data.curves);
  const labels = { AWS: 'AWS', GCP: 'Google Cloud', 'On premises': 'Owned infrastructure' };
  svg.insertAdjacentHTML('beforeend', `<g class="chart-inspector" display="none" pointer-events="none">
    <line y1="${T}" y2="${H-B}" stroke="#516f88" stroke-dasharray="3 3"/>
    ${series.map(([name]) => `<circle r="4" fill="${colors[name]}" stroke="white" stroke-width="1.5"/>`).join('')}
    <g class="chart-tooltip" font-size="12" fill="#183f69">
      <rect width="236" height="102" rx="7" fill="white" stroke="#b6cfe1"/>
      <text x="12" y="20" font-weight="700"></text>
      ${series.map(([name], i) => `<circle cx="13" cy="${38+i*23}" r="3" fill="${colors[name]}"/>
        <text x="22" y="${42+i*23}">${labels[name]}</text><text class="cost" x="225" y="${42+i*23}" text-anchor="end"></text>`).join('')}
    </g></g>`);
  const inspector = svg.querySelector('.chart-inspector');
  const guide = inspector.querySelector('line');
  const dots = inspector.querySelectorAll(':scope > circle');
  const tooltip = inspector.querySelector('.chart-tooltip');
  const costs = tooltip.querySelectorAll('.cost');
  function inspect(event) {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
    if (point.x < L || point.x > W-R || point.y < T || point.y > H-B) {
      inspector.setAttribute('display', 'none');
      return;
    }
    const month = Math.round((point.x-L) * maxMonth / (W-L-R));
    const position = x(month);
    guide.setAttribute('x1', position);
    guide.setAttribute('x2', position);
    series.forEach(([, values], i) => {
      dots[i].setAttribute('cx', position);
      dots[i].setAttribute('cy', y(values[month]));
      costs[i].textContent = money(values[month]);
    });
    tooltip.querySelector('text').textContent = `Month ${data.month_axis[month]}`;
    const left = position + 248 <= W-R ? position + 12 : position - 248;
    tooltip.setAttribute('transform', `translate(${left} ${Math.min(point.y + 10, H-B-102)})`);
    inspector.removeAttribute('display');
  }
  svg.onpointermove = svg.onpointerdown = inspect;
  svg.onpointerleave = svg.onpointercancel = () => inspector.setAttribute('display', 'none');
  svg.setAttribute('aria-label',`Cumulative cost across ${maxMonth} months. AWS break-even: ${data.breakeven_month.AWS ?? 'none'} months. GCP break-even: ${data.breakeven_month.GCP ?? 'none'} months.`);
}
function render(data) {
  currentResults = data;
  const comparison=data.cloud_month.GCP <= data.cloud_month.AWS ? 'GCP' : 'AWS';
  const month=data.breakeven_month[comparison];
  const horizon=data.inputs.horizon_months;
  const ownedTotal=data.curves['On premises'].at(-1);
  const cloudTotal=data.curves[comparison].at(-1);
  document.querySelector('#leadPrefix').textContent=month ? 'Ownership first pulls ahead in ' : 'No crossover with the lower-cost cloud';
  document.querySelector('#leadMonth').textContent=month ? `month ${month}` : '';
  document.querySelector('#leadCopy').textContent=month ? `Against ${comparison === 'GCP' ? 'Google Cloud' : 'AWS'}, the lower-cost cloud option at these inputs. Hardware refreshes can reverse the lead later.` : `Owned hardware does not cross below ${comparison === 'GCP' ? 'Google Cloud' : 'AWS'} within ${horizon} months.`;
  document.querySelector('#horizonVerdict').textContent=ownedTotal < cloudTotal ? 'Owned costs less' : `${comparison === 'GCP' ? 'Google Cloud' : 'AWS'} costs less`;
  document.querySelector('#horizonCopy').textContent=`${money(ownedTotal)} owned vs ${money(cloudTotal)} cloud at ${horizon} months`;
  document.querySelector('#awsMonth').textContent=money(data.cloud_month.AWS);
  document.querySelector('#gcpMonth').textContent=money(data.cloud_month.GCP);
  document.querySelector('#onMonth').textContent=money(data.onprem_month);
  document.querySelector('#cloudBreakdown').innerHTML='<h4>AWS</h4>'+rows(data.cloud_parts.AWS,data.cloud_month.AWS)+'<h4>Google Cloud</h4>'+rows(data.cloud_parts.GCP,data.cloud_month.GCP);
  document.querySelector('#onBreakdown').innerHTML=`<p class="muted">${data.drive_count} drives · ${data.enclosure_count} enclosures · ${Math.round(data.raw_storage_tb).toLocaleString()} TB raw · ${data.it_kw.toFixed(1)} kW IT load · ${money(data.hardware_refresh_cost)} every ${data.inputs.hardware_life_months} months</p><h4>Upfront</h4>`+rows(data.onprem_capex_parts,data.onprem_capex)+'<h4>Monthly</h4>'+rows(data.onprem_month_parts,data.onprem_month);
  document.querySelector('#breakEven').innerHTML=Object.entries(data.cheaper_windows).map(([name,windows])=>`<div><strong>${name}</strong>: ${windows.length?`on-prem cheaper in month${windows.length===1&&windows[0][0]===windows[0][1]?'':'s'} ${windows.map(([start,end])=>start===end?start:`${start}–${end}`).join(', ')}`:'no break-even within the horizon'}</div>`).join('');
  draw(data);
}
async function calculate(inputs) {
  const version = ++calculationVersion;
  try {
    const response=await fetch('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(inputs)});
    const data=await response.json();
    if (version !== calculationVersion) return;
    if (!response.ok) throw new Error(data.error || 'Calculation failed');
    document.querySelector('#error').hidden=true;
    render(data);
  } catch(error) {
    if (version !== calculationVersion) return;
    const el=document.querySelector('#error');el.textContent=error.message;el.hidden=false;
  }
}
form.addEventListener('submit',e=>{e.preventDefault();calculate(getInputs())});
form.addEventListener('change',()=>calculate(getInputs()));
let pendingRecalculation;
form.addEventListener('input',()=>{
  clearTimeout(pendingRecalculation);
  if (form.checkValidity()) pendingRecalculation=setTimeout(()=>calculate(getInputs()),250);
});
let calculationVersion = 0;
let refreshVersion = 0;
const refreshButton = document.querySelector('#refreshPrices');
const priceStatus = document.querySelector('#priceStatus');
refreshButton.addEventListener('click', async () => {
  const version = ++refreshVersion;
  refreshButton.disabled = true;
  priceStatus.hidden = false;
  priceStatus.textContent = 'Fetching official AWS and Google Cloud rates…';
  try {
    const response = await fetch('/api/prices/refresh', {method:'POST', headers:{'Content-Type':'application/json'}});
    const result = await response.json();
    if (version !== refreshVersion) return;
    if (!response.ok) throw new Error(result.error);
    setInputs(result.rates);
    clearTimeout(pendingRecalculation);
    priceStatus.textContent = 'Official rates fetched ' + new Date(result.fetched_at).toLocaleString() + '.';
    await calculate(getInputs());
  } catch (error) {
    if (version === refreshVersion) priceStatus.textContent = error.message;
  } finally {
    if (version === refreshVersion) refreshButton.disabled = false;
  }
});
document.querySelector('#reset').addEventListener('click',()=>{
  if (!defaults) return;
  ++refreshVersion;
  refreshButton.disabled = false;
  priceStatus.hidden = true;
  clearTimeout(pendingRecalculation);
  setInputs(defaults);
  calculate(defaults);
});
fetch('/api/defaults').then(r=>r.json()).then(data=>{defaults=data.inputs;setInputs(defaults);render(data);refreshButton.disabled=false}).catch(e=>{const el=document.querySelector('#error');el.textContent=e.message;el.hidden=false});

