document.addEventListener("DOMContentLoaded", function () {
  const options = { threshold: 0.1 };
  const observer = new IntersectionObserver((entries) => {
    // 一度に複数交差する可能性があるので、並び順に合わせて処理したい
    // そこで交差した要素をまとめてソートし、順番に遅延付与します

    // 見えているエントリだけ抽出
    const visibleEntries = entries.filter(entry => entry.isIntersecting);

    // DOMの位置順にソート（親要素内で左→右→下方向順）
    visibleEntries.sort((a, b) => {
      return a.target.compareDocumentPosition(b.target) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });

    visibleEntries.forEach((entry, index) => {
      setTimeout(() => {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }, index * 400); // 0.4秒ずつ遅延
    });
  }, options);

  // 観測対象
  document.querySelectorAll('.fade-in-text, .fade-in-img').forEach(el => {
    observer.observe(el);
  });

  // ここで一括で visible 付けてる images 処理は残してOK
  const images = document.querySelectorAll('.fade-in-up, .card-img-top');
  images.forEach(img => {
    img.classList.add('visible');
  });

  // animated-login-title の hover animation 処理も残す
  const letters = document.querySelectorAll('.animated-login-title span');
  letters.forEach(letter => {
    letter.addEventListener('mouseenter', () => {
      letter.classList.add('hover-animate');

      letter.addEventListener('animationend', () => {
        letter.classList.remove('hover-animate');
      }, { once: true });
    });
  });
});
