/* ===== 1. Анимации при появлении элементов ===== */
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.card, .list-group-item, .alert').forEach(el => {
  el.classList.add('fade-in');
  observer.observe(el);
});


/* ===== 2. Подсветка активной карточки при наведении ===== */
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('mouseenter', function () {
    this.style.transform = 'translateY(-3px)';
    this.style.boxShadow = '0 6px 20px rgba(111, 66, 193, 0.12)';
    this.style.borderColor = '#c4b5f5';
    this.style.transition = 'all 0.2s ease';
  });
  card.addEventListener('mouseleave', function () {
    this.style.transform = '';
    this.style.boxShadow = '';
    this.style.borderColor = '';
  });
});


/* ===== 3. Интерактивный счётчик баллов в калькуляторе ===== */
function initScoreCounter() {
  const totalEl = document.getElementById('total-score-counter');
  if (!totalEl) return;

  const inputs = document.querySelectorAll('.score-input');
  if (!inputs.length) return;

  function updateTotal() {
    let total = 0;
    inputs.forEach(inp => {
      const val = parseInt(inp.value) || 0;
      total += Math.min(100, Math.max(0, val));

      // Цветовая индикация поля
      inp.classList.remove('border-success', 'border-warning', 'border-danger');
      if (val >= 80)      inp.classList.add('border-success');
      else if (val >= 60) inp.classList.add('border-warning');
      else if (val > 0)   inp.classList.add('border-danger');
    });

    // Анимированный счётчик
    animateCount(totalEl, parseInt(totalEl.textContent) || 0, total);

    // Цвет итогового балла
    totalEl.className = 'fw-semibold fs-4';
    if (total >= 240)      totalEl.classList.add('text-success');
    else if (total >= 180) totalEl.classList.add('text-warning');
    else if (total > 0)    totalEl.classList.add('text-danger');
    else                   totalEl.classList.add('text-muted');
  }

  function animateCount(el, from, to) {
    const duration = 400;
    const start = performance.now();
    function step(now) {
      const progress = Math.min((now - start) / duration, 1);
      el.textContent = Math.round(from + (to - from) * progress);
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  inputs.forEach(inp => inp.addEventListener('input', updateTotal));
  updateTotal();
}

document.addEventListener('DOMContentLoaded', () => {
  initScoreCounter();
});