// main.js - modern UI helpers, handlers and clocks
function showToast(id, msg){
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove("d-none");


  // fade-in + bounce
  setTimeout(() => {
    el.classList.add("show", "animate");
  }, 10);

  // hide after 3 seconds
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => {
      el.classList.add("d-none");
      el.classList.remove("animate");
    }, 300);
  }, 3000);
}

// Error toast
function showError(msg){
  showToast("error-toast", msg);
}

// Success toast
function showSuccess(msg){
  showToast("success-toast", msg);
}

function playSound(audioId) {
  const audio = document.getElementById(audioId);
  if (!audio) return;

  audio.currentTime = 0;
  audio.muted = false;
  audio.volume = 0.8;

  audio.play().catch(() => {});
}


function showConfirm({icon, title, desc, okText = "OK", okClass="btn-primary"}) {
  return new Promise(resolve => {

    const overlay = document.getElementById("confirm-overlay");
    const iconEl = document.getElementById("confirm-icon");
    const titleEl = document.getElementById("confirm-title");
    const descEl = document.getElementById("confirm-desc");
    const cancelBtn = document.getElementById("confirm-cancel");
    const okBtn = document.getElementById("confirm-ok");

    iconEl.className = icon;
    titleEl.textContent = title;
    descEl.textContent = desc;

    okBtn.textContent = okText;
    okBtn.className = `btn flex-fill ${okClass}`;

    overlay.classList.remove("d-none");

    cancelBtn.onclick = () => {
      overlay.classList.add("d-none");
      resolve(false);
    };

    okBtn.onclick = () => {
      overlay.classList.add("d-none");
      resolve(true);
    };

  });
}




async function post(url){
  const res = await fetch(url, {method: 'POST'});
  return res.json();
}

function showError(msg){
  const toast = document.getElementById("error-toast");
  toast.textContent = msg;
  toast.classList.remove("d-none");

  // trigger fade-in
  setTimeout(() => toast.classList.add("show"), 10);

  // hide after 3 seconds
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.classList.add("d-none"), 300);
  }, 3000);
}



window.addEventListener('DOMContentLoaded', ()=>{

  // Buttons
  const startBtn = document.getElementById('start-btn');
  const doneBtn = document.getElementById('done-btn');
  const resetBtn = document.getElementById('reset-btn');
  const showOtBtn = document.getElementById('show-ot');
// RESET WARNING CARD
const resetOverlay = document.getElementById("reset-warning");
const cancelReset = document.getElementById("cancel-reset");
const confirmReset = document.getElementById("confirm-reset");





  if(startBtn) startBtn.addEventListener('click', async ()=>{

  // 1️⃣ Check if already on duty
  const status = await fetch("/is_on_duty").then(r => r.json());
  if(status.on_duty){
playSound('duplicated-audio');
    showError("Duplicated punch!");
    return;
  }

  // 2️⃣ Not on duty → show confirmation box
  const ok = await showConfirm({
    icon: "bi bi-play-circle-fill text-success",
    title: "Start Duty?",
    desc: "Your working time will start now.",
    okText: "Start Now",
    okClass: "btn-success"
  });

  if(!ok) return;

  // 3️⃣ Actually start duty
  const r = await post("/start");

  if(!r.ok){
    showError(r.error);
    return;
  }
  playSound('start-audio');
  showSuccess("Thank you, Duty Started!");
  setTimeout(()=>location.reload(), 2200);
});



  if(doneBtn) doneBtn.addEventListener('click', async ()=>{

  // 1️⃣ Check if user is on duty
  const status = await fetch("/is_on_duty").then(r => r.json());

  if(!status.on_duty){
    showError("You have not started duty yet!");
    return;
  }

  // 2️⃣ Show confirm box if duty is active
  const ok = await showConfirm({
    icon: "bi bi-stop-circle-fill text-primary",
    title: "Finish Duty?",
    desc: "Your work duration will be saved.",
    okText: "Finish",
    okClass: "btn-primary"
  });

  if(!ok) return;

  // 3️⃣ Finish the duty
  const r = await post("/done");

  if(!r.ok){
    showError(r.error || "Unable to finish duty.");
    return;
  }
  playSound('done-audio')
  showSuccess("Duty Finished!");
  setTimeout(()=>location.reload(), 1500);
});



  if(resetBtn){
  resetBtn.addEventListener("click", async ()=>{

    // 1️⃣ Check if any history exists
     
    const status = await fetch("/has_history").then(r => r.json());

    if(!status.has_history){
      showError("Nothing to reset!");
      return;
    }

    // 2️⃣ Show confirm card ONLY if history exists
    const ok = await showConfirm({
      icon: "bi bi-x-circle-fill text-danger",
      title: "Reset All Data?",
      desc: "All duty history and sessions will be permanently deleted.",
      okText: "Reset",
      okClass: "btn-danger"
    });

    if(!ok) return;

    // 3️⃣ Perform reset
    const r = await post("/reset");

    if(r.ok){
      showSuccess("All data reset!");
      setTimeout(()=>location.reload(), 700);
    } else {
      showError("Something went wrong!");
    }
  });
}



  if(showOtBtn) showOtBtn.addEventListener('click', async ()=>{
    const day = document.getElementById('day-input').value;
    if(!day){ alert('Pick a date first'); return; }
    const res = await fetch('/overtime_total?day='+encodeURIComponent(day));
    const j = await res.json();
    const h = Math.floor(j.seconds/3600), m = Math.floor((j.seconds%3600)/60);
    const oh = Math.floor(j.overtime/3600), om = Math.floor((j.overtime%3600)/60);
    document.getElementById('ot-result').innerHTML = `<div>Worked: ${h}h ${m}m — Overtime: ${oh}h ${om}m</div>`;
  });

  // local clock
  const clockEl = document.getElementById('local-clock');
  function updateClock(){
    if(!clockEl) return;
    const d = new Date();
    const opts = { year:'numeric', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false };
    clockEl.textContent = d.toLocaleString(undefined, opts);
  }
  updateClock();
  setInterval(updateClock, 1000);

  // running timer: read ISO start from body data attribute
  const runningEl = document.getElementById('running-timer');
  const body = document.body;
  const startIso = body ? body.getAttribute('data-ongoing-start-iso') : null;
  if(startIso && runningEl){
    // parse with Date so timezone included
    let start = new Date(startIso);
    function updateRunning(){
      const now = new Date();
      let diff = Math.floor((now - start) / 1000);
      if(diff < 0) diff = 0;
      const h = Math.floor(diff/3600); diff %= 3600;
      const m = Math.floor(diff/60); const s = diff % 60;
      runningEl.textContent = `${h}h ${m}m ${s}s`;
    }
    updateRunning();
    setInterval(updateRunning, 1000);
  }


// Format number to 2 decimals
function fmtMoney(x){
  return Number(x).toFixed(2);
}

async function renderEarnings(rate, day=null){
  // call backend
  const url = '/overtime_earnings?rate=' + encodeURIComponent(rate) + (day ? ('&day=' + encodeURIComponent(day)) : '');
  const res = await fetch(url);
  const j = await res.json();
  if(j.error){
    showError(j.error);
    return;
  }

  // build HTML: simple breakdown + total
  const rows = j.rows || [];
  if(rows.length === 0){
    document.getElementById('earn-result').innerHTML = '<div class="text-muted">No records to calculate.</div>';
    return;
  }

  let html = `<div class="small text-muted mb-2">Earnings breakdown</div>`;
  html += `<div class="table-responsive"><table class="table table-sm mb-0"><thead class="table-light"><tr><th>Date</th><th>OT Hours</th><th>Earning</th></tr></thead><tbody>`;
  rows.forEach(r => {
    const hrs = Number(r.overtime_hours).toFixed(2);
    const earn = fmtMoney(r.earning);
    html += `<tr><td class="fw-medium">${r.day}</td><td>${hrs}</td><td>${earn}</td></tr>`;
  });
  html += `</tbody></table></div>`;
  html += `<div class="mt-2 fw-semibold">Total: ${fmtMoney(j.total_earning)}</div>`;

  document.getElementById('earn-result').innerHTML = html;
}


// Compute OT hourly rate
function computeOTRate(salary){
  const wdpm = 26;               // working days per month
  const monthly_hours = 8 * wdpm;
  const hourly = salary / monthly_hours;
  const ot_hourly = hourly * 1.3; // 130% OT factor
  return Number(ot_hourly.toFixed(2));
}

// Slide-down reveal for OT rate
function showOTRate(rate){
  const line = document.getElementById("ot-rate-line");
  const val = document.getElementById("ot-rate-value");
  if(!line || !val) return;

  // set value
  val.textContent = rate;

  // If already visible, just update value
  if(!line.classList.contains('d-none') && line.classList.contains('slide-down')){
    return;
  }

  // prepare: remove d-none so it participates in layout for animation
  line.classList.remove('d-none');

  // start from "prep" state then animate to slide-down
  line.classList.add('prep-show');
  // force a reflow so the prep-show class takes effect before animation
  // eslint-disable-next-line no-unused-expressions
  line.offsetHeight; // force reflow

  // remove prep, add slide-down
  line.classList.remove('prep-show', 'slide-up');
  line.classList.add('slide-down');

  // remove slide-down class after animation completes to keep DOM clean (optional)
  setTimeout(()=>{
    // ensure it's still visible
    if(line.classList.contains('slide-down')){
      line.classList.remove('slide-down');
      // keep it visible by ensuring d-none is removed and opacity is 1 via inline style if needed
      line.style.maxHeight = '120px';
      line.style.opacity = '1';
    }
  }, 320); // slightly longer than CSS transition to be safe
}

function hideOTRate(){
  const line = document.getElementById("ot-rate-line");
  if(!line) return;
  // if already hidden, do nothing
  if(line.classList.contains('d-none')) return;

  // start slide-up animation
  line.classList.remove('slide-down', 'prep-show');
  line.classList.add('slide-up');

  // after transition, add d-none to remove from flow
  setTimeout(()=>{
    line.classList.add('d-none');
    // cleanup classes & inline styles
    line.classList.remove('slide-up');
    line.style.maxHeight = '';
    line.style.opacity = '';
  }, 300); // should match the CSS transition duration (260ms + small buffer)
}

// ----- Salary settings integration -----
async function fetchSavedSalary(){
  const res = await fetch('/get_salary');
  const j = await res.json();
  return (j.has_salary ? j.salary : null);
}

async function setSavedSalary(val){
  return await fetch('/set_salary', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({salary: Number(val)})
  }).then(r => r.json());
}

// On load: fill salary + show OT rate
(async ()=>{
  const saved = await fetchSavedSalary();
  const salaryEl = document.getElementById('user-salary');
  const rateEl = document.getElementById('earn-rate');

  if(saved){
    salaryEl.value = saved;
    const otRate = computeOTRate(saved);
    showOTRate(otRate);
    if(rateEl) rateEl.value = otRate; // autofill for earnings calc
  }

  // Save salary
  const saveBtn = document.getElementById("save-salary");
  if(saveBtn){
    saveBtn.addEventListener("click", async ()=>{
      const v = Number(salaryEl.value);
      if(!v || v <= 0){ showError("Enter valid salary"); return; }

      saveBtn.disabled = true;
      const res = await setSavedSalary(v);
      saveBtn.disabled = false;

      if(!res.ok){ showError("Could not save salary"); return; }

      const otRate = computeOTRate(v);
      showOTRate(otRate);
      if(rateEl) rateEl.value = otRate;
      showSuccess("Salary saved!");
    });
  }

  // Clear salary
  const clearBtn = document.getElementById("clear-salary");
  if(clearBtn){
    clearBtn.addEventListener("click", async ()=>{
      const res = await setSavedSalary(0);

      if(res.ok){
        salaryEl.value = "";
        hideOTRate();
        if(rateEl) rateEl.value = "";
        showSuccess("Salary cleared");
      } else {
        showError("Could not clear salary");
      }
    });
  }
})();

  // Clear salary button
  const clearSalBtn = document.getElementById('clear-salary');
  if(clearSalBtn){
    clearSalBtn.addEventListener('click', async ()=>{
      if(!confirm){ /* fallback; do nothing */ }
      // to actually remove, we'll set salary=0 which our get_salary treats as missing
      clearSalBtn.disabled = true;
      const res = await setSavedSalary(0);
      clearSalBtn.disabled = false;
      if(!res.ok){ showError('Could not clear'); return; }
     // if(salaryEl) salaryEl.value = '';
      if(rateEl) rateEl.value = '';
      showSuccess('Saved salary cleared');
    });
  }

// Earnings calculator - Uses salary ONLY
const calcBtn = document.getElementById('calc-earn');
const clearBtn = document.getElementById('clear-earn');

if (calcBtn) {
  calcBtn.addEventListener('click', async () => {

    // Get saved salary
    const savedSalary = await fetchSavedSalary();
    const dayVal = document.getElementById('earn-day').value;

    if (!savedSalary || savedSalary <= 0) {
      showError("Save your salary first in Settings.");
      return;
    }

    calcBtn.disabled = true;

    // Call salary-based OT calculator
    const url = '/overtime_from_salary?salary=' +
      encodeURIComponent(savedSalary) +
      (dayVal ? ('&day=' + encodeURIComponent(dayVal)) : '');

    const res = await fetch(url);
    const j = await res.json();

    if (j.error) {
      showError(j.error);
      calcBtn.disabled = false;
      return;
    }

    // Render table
    const rows = j.rows || [];
    if (rows.length === 0) {
      document.getElementById('earn-result').innerHTML =
        '<div class="text-muted">No records to calculate.</div>';
      calcBtn.disabled = false;
      return;
    }

    let html = `<div class="small text-muted mb-2">OT Rate: <strong>${j.ot_rate_hour}</strong> per hour</div>
                <div class="table-responsive">
                  <table class="table table-sm mb-0">
                    <thead class="table-light">
                      <tr><th>Date</th><th>OT Hours</th><th>Earning</th></tr>
                    </thead><tbody>`;

    rows.forEach(r => {
      const hrs = Number(r.overtime_hours).toFixed(2);
      const earn = Number(r.earning).toFixed(2);
      html += `<tr>
                <td class="fw-medium">${r.day}</td>
                <td>${hrs}</td>
                <td>${earn}</td>
               </tr>`;
    });

    html += `</tbody></table></div>`;
    html += `<div class="mt-2 fw-semibold">Total: ${Number(j.total_earning).toFixed(2)}</div>`;

    document.getElementById('earn-result').innerHTML = html;
    calcBtn.disabled = false;
  });
}

if (clearBtn) {
  clearBtn.addEventListener('click', () => {
    document.getElementById('earn-day').value = '';
    document.getElementById('earn-result').innerHTML = '';
  });
}




});