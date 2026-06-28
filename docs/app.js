// ── Navbar scroll ──────────────────────────────────────────────────────────
const nav = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
}, { passive: true });

// ── Animated grid canvas ───────────────────────────────────────────────────
const canvas = document.getElementById('gridCanvas');
const ctx = canvas.getContext('2d');
function resizeCanvas() {
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
}
resizeCanvas();
window.addEventListener('resize', resizeCanvas);
function drawGrid() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const size = 60;
  ctx.strokeStyle = 'rgba(99,102,241,0.25)';
  ctx.lineWidth = 0.5;
  for (let x = 0; x <= canvas.width; x += size) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y <= canvas.height; y += size) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }
}
drawGrid();

// ── Copy install command ───────────────────────────────────────────────────
function copyCmd() {
  const text = 'pip install axon-bridge && axon serve';
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copyBtn');
    const ico = document.getElementById('copyIco');
    btn.style.color = '#10b981';
    ico.innerHTML = '<polyline points="20 6 9 17 4 12" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
    setTimeout(() => {
      btn.style.color = '';
      ico.innerHTML = '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>';
    }, 2000);
  });
}

// ── Animated stat counters ─────────────────────────────────────────────────
function animateCounter(el, target, duration = 1600) {
  let start = null;
  const step = (ts) => {
    if (!start) start = ts;
    const progress = Math.min((ts - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 4);
    el.textContent = Math.round(ease * target);
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

const io = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const el = entry.target;
      const target = parseInt(el.dataset.target);
      if (!isNaN(target)) animateCounter(el, target);
      io.unobserve(el);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-target]').forEach(el => io.observe(el));

// ── Scroll reveal ──────────────────────────────────────────────────────────
const revealObs = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      revealObs.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

// Add reveal class to animatable elements
const selectors = [
  '.feat', '.s-card', '.pipe-card', '.prov-card',
  '.bench-table-wrap', '.strategy-section', '.qs-step',
  '.code-pane', '.hdr-card', '.rhdr'
];
selectors.forEach(sel => {
  document.querySelectorAll(sel).forEach((el, i) => {
    el.classList.add('reveal');
    el.style.transitionDelay = `${(i % 6) * 0.07}s`;
    revealObs.observe(el);
  });
});

// ── Active nav highlight ───────────────────────────────────────────────────
const sections = document.querySelectorAll('section[id], div[id]');
const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

const sectionObs = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      navLinks.forEach(a => {
        a.style.color = a.getAttribute('href') === '#' + entry.target.id ? '#e2e2f0' : '';
      });
    }
  });
}, { rootMargin: '-40% 0px -55% 0px' });

sections.forEach(s => sectionObs.observe(s));

// ── Smooth anchor scroll with offset ──────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      const offset = 72;
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - offset, behavior: 'smooth' });
    }
  });
});
