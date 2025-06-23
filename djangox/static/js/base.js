document.addEventListener("DOMContentLoaded", () => {
  // IntersectionObserverでフェードイン処理
  const options = { threshold: 0.1 };
  const observer = new IntersectionObserver((entries) => {
    const visibleEntries = entries.filter(e => e.isIntersecting);
    visibleEntries.sort((a, b) => 
      a.target.compareDocumentPosition(b.target) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
    );

    visibleEntries.forEach((entry, i) => {
      setTimeout(() => {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }, i * 300);
    });
  }, options);

  document.querySelectorAll('.fade-in-text, .fade-in-img').forEach(el => observer.observe(el));

  // 画像は即visible付与
  document.querySelectorAll('.fade-in-up, .card-img-top').forEach(img => img.classList.add('visible'));

  // カルーセル設定
  const carousel = document.querySelector('.movie-carousel');
  if (!carousel) return;

  const scrollStep = 304;
  let autoScroll = true;
  let scrollInterval = setInterval(autoScrollCarousel, 5000); // ← 戻り値保持

  const items = carousel.querySelectorAll('.movie-item');
  for (let i = 0; i < Math.min(5, items.length); i++) {
    const clone = items[i].cloneNode(true);
    carousel.appendChild(clone);
    // クローンされた要素もフェードイン対象なら再監視
    if (clone.matches('.fade-in-text, .fade-in-img')) {
      observer.observe(clone);
    }
  }

  function autoScrollCarousel() {
    if (!autoScroll) return;

    const atEnd = Math.ceil(carousel.scrollLeft + carousel.clientWidth) >= carousel.scrollWidth - 1;
    if (atEnd) {
      carousel.scrollLeft = 0;
    } else {
      carousel.scrollBy({ left: scrollStep, behavior: 'smooth' });
    }
  }

  function manualScroll(direction) {
    const maxScrollLeft = carousel.scrollWidth - carousel.clientWidth;
    let targetScrollLeft = carousel.scrollLeft + direction * scrollStep;

    if (targetScrollLeft >= maxScrollLeft - 5) {
      targetScrollLeft = 0;
    } else if (targetScrollLeft <= 5) {
      targetScrollLeft = maxScrollLeft;
    }

    carousel.scrollTo({ left: targetScrollLeft, behavior: 'smooth' });
  }

  // ボタン操作
  const leftBtn = document.getElementById('scroll-left');
  const rightBtn = document.getElementById('scroll-right');

  function setupButtonScroll(btn, direction) {
    if (!btn) return;

    let intervalId;
    btn.addEventListener('mousedown', () => {
      autoScroll = false;
      intervalId = setInterval(() => manualScroll(direction), 100);
    });

    const stopScroll = () => {
      clearInterval(intervalId);
      autoScroll = true;
    };

    btn.addEventListener('mouseup', stopScroll);
    btn.addEventListener('mouseleave', stopScroll);
    btn.addEventListener('touchend', stopScroll); // スマホ対応
  }

  setupButtonScroll(leftBtn, -1);
  setupButtonScroll(rightBtn, 1);

  // 外部からも呼び出せるように
  window.slideMovies = manualScroll;
  window.scrollCarousel = manualScroll;

  const btn = document.querySelector(".openbtn");
  const nav = document.getElementById("g-nav");

  btn?.addEventListener("click", () => {
    btn.classList.toggle("active");
    nav.classList.toggle("panelactive");
  });
});

