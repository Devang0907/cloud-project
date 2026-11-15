const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n);
const axisMoney = n => n >= 1e6 ? `$${(n/1e6).toFixed(1)}m` : n >= 1e3 ? `$${Math.round(n/1e3)}k` : `$${Math.round(n)}`;
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
  const colors={AWS:'#277bc2',GCP:'#55b7e8','On premises':'#0e5f9f'};
  const lines=Object.entries(data.curves).map(([name,values])=>`<polyline fill="none" stroke="${colors[name]}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" points="${values.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}"/>`).join('');
  const comparison=data.cloud_month.GCP <= data.cloud_month.AWS ? 'GCP' : 'AWS';
  const crossover=data.breakeven_month[comparison];
  const marker=crossover ? `<line x1="${x(crossover)}" x2="${x(crossover)}" y1="${T}" y2="${H-B}" stroke="#197fc0" stroke-width="1.3" stroke-dasharray="5 5"/><text x="${x(crossover)+7}" y="${T+12}" fill="#126da9" font-size="12" font-weight="700">MONTH ${crossover}</text>` : '';
  svg.innerHTML=grid+ticks+marker+lines;
  svg.setAttribute('aria-label',`Cumulative cost across ${maxMonth} months. AWS break-even: ${data.breakeven_month.AWS ?? 'none'} months. GCP break-even: ${data.breakeven_month.GCP ?? 'none'} months.`);
}
function render(data) {
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
  try {
    const response=await fetch('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(inputs)});
    const data=await response.json();
    if (!response.ok) throw new Error(data.error || 'Calculation failed');
    document.querySelector('#error').hidden=true;
    render(data);
  } catch(error) {
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
document.querySelector('#reset').addEventListener('click',()=>{clearTimeout(pendingRecalculation);setInputs(defaults);calculate(defaults)});
fetch('/api/defaults').then(r=>r.json()).then(data=>{defaults=data.inputs;setInputs(defaults);render(data)}).catch(e=>{const el=document.querySelector('#error');el.textContent=e.message;el.hidden=false});

