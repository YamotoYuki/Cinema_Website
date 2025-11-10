document.addEventListener("DOMContentLoaded", function () {
  const options = { threshold: 0.1 };
  const observer = new IntersectionObserver((entries) => {
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

  // 座席選択処理
  const seatingDiv = document.getElementById('seating');
  const selectedSeatsSpan = document.getElementById('selected-seats');
  const seatInput = document.getElementById('seatInput');

  const rows = ['A','B','C','D','E','F','G','H','I','J'];
  const leftCols = Array.from({length: 4}, (_, i) => i + 1);
  const centerCols = Array.from({length: 12}, (_, i) => i + 5);
  const rightCols = Array.from({length: 4}, (_, i) => i + 17);

  let selectedSeats = [];
  const reservedSeats = ['C7', 'C8', 'D10', 'E15']; 
  const wheelchairSeats = ['A5', 'A6', 'A15', 'A16']; 

rows.forEach(row => {
  seatingDiv.appendChild(makeLabel(row, 'left')); 

  leftCols.forEach(num => seatingDiv.appendChild(makeSeat(row, num)));

  seatingDiv.appendChild(makeSpacer(row)); 

  centerCols.forEach(num => seatingDiv.appendChild(makeSeat(row, num)));

  seatingDiv.appendChild(makeSpacer(row)); 

  rightCols.forEach(num => seatingDiv.appendChild(makeSeat(row, num)));

  seatingDiv.appendChild(makeLabel(row, 'right')); 
});

  function makeSeat(row, num) {
    const seat = document.createElement('div');
    const seatId = `${row}${num}`;
    seat.className = 'seat';
    seat.textContent = num;
    seat.dataset.seatId = seatId;

    if (reservedSeats.includes(seatId)) {
      seat.classList.add('reserved');
      seat.style.pointerEvents = 'none';
    } else if (wheelchairSeats.includes(seatId)) {
      seat.classList.add('wheelchair');
    }

    seat.addEventListener('click', () => {
      if (seat.classList.contains('reserved')) return;

      seat.classList.toggle('selected');
      if (selectedSeats.includes(seatId)) {
        selectedSeats = selectedSeats.filter(s => s !== seatId);
      } else {
        selectedSeats.push(seatId);
      }
      updateSelectedSeats();
    });

    return seat;
  }

function makeLabel(row, position) {
  const div = document.createElement('div');
  div.className = 'seat label';
  if (position === 'left' || position === 'right') {
    div.textContent = ''; 
  } else {
    div.textContent = row;  
  }
  return div;
}

function makeSpacer(row) {
  const div = document.createElement('div');
  div.className = 'seat label';
  div.textContent = row;
  return div;
}

  function updateSelectedSeats() {
    selectedSeatsSpan.textContent = selectedSeats.length > 0 ? selectedSeats.join(', ') : 'なし';
    seatInput.value = selectedSeats.join(',');
  }
});
