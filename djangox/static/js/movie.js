// movie.js - 映画予約システムの統合JavaScript

document.addEventListener("DOMContentLoaded", function () {
  // ========================================
  // 曜日別の上映時間スロット管理
  // ========================================
  const dateRadios = document.querySelectorAll('input[name="date"]');
  const timeSlotContainer = document.getElementById('time-slot-container');

  const timeSlotMap = {
    "月": ["09:00～11:00","11:00～13:00","15:00～17:00", "17:00～19:00","19:00～21:00","21:00～23:00"],
    "火": ["09:00～11:00","11:00～13:00","13:00～15:00", "15:00～17:00", "17:00～19:00","19:00～21:00"],
    "水": ["09:00～11:00","13:00～15:00","15:00～17:00", "17:00～19:00","19:00～21:00","21:00～23:00"],
    "木": ["11:00～13:00","13:00～15:00", "15:00～17:00", "17:00～19:00","19:00～21:00"],
    "金": ["09:00～11:00","11:00～13:00","13:00～15:00", "15:00～17:00", "17:00～19:00"],
    "土": ["09:00～11:00","11:00～13:00","13:00～15:00", "15:00～17:00", "17:00～19:00","19:00～21:00","21:00～23:00"],
    "日": ["09:00～11:00","11:00～13:00","13:00～15:00", "15:00～17:00", "17:00～19:00","19:00～21:00","21:00～23:00"]
  };

  function updateTimeSlots(weekday) {
    const slots = timeSlotMap[weekday] || [];
    timeSlotContainer.innerHTML = '';

    const now = new Date();
    const selectedDateInput = document.querySelector('input[name="date"]:checked');
    const selectedDateStr = selectedDateInput ? selectedDateInput.value : null;
    const isToday = selectedDateStr === now.toISOString().split('T')[0];

    slots.forEach((slot, index) => {
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'time_slot';
      input.className = 'btn-check';
      input.id = 'time' + index;
      input.value = slot;

      const label = document.createElement('label');
      label.className = 'btn time-label btn-outline-secondary';
      label.setAttribute('for', 'time' + index);
      label.textContent = slot;

      if (isToday) {
        const startHour = parseInt(slot.split('～')[0].split(':')[0]);
        const startMin = parseInt(slot.split('～')[0].split(':')[1]);
        const slotTime = new Date(now);
        slotTime.setHours(startHour, startMin, 0, 0);

        if (slotTime < now) {
          input.disabled = true;
          label.classList.remove('btn-outline-secondary');
          label.classList.add('btn-danger');
        }
      }

      if (index === 0 && !input.disabled) input.checked = true;

      timeSlotContainer.appendChild(input);
      timeSlotContainer.appendChild(label);
    });
  }

  // 初期表示
  if (timeSlotContainer) {
    const selected = document.querySelector('input[name="date"]:checked');
    if (selected) updateTimeSlots(selected.dataset.weekday);

    dateRadios.forEach(radio => {
      radio.addEventListener('change', () => {
        updateTimeSlots(radio.dataset.weekday);
      });
    });
  }

  // ========================================
  // お気に入り機能
  // ========================================
  const favoriteBtn = document.getElementById('favoriteBtn');
  
  if (favoriteBtn) {
    const movieId = favoriteBtn.dataset.movieId;
    
    function updateFavoriteButton() {
      const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
      const isFavorite = favorites.includes(movieId);
      
      if (isFavorite) {
        favoriteBtn.classList.add('active');
        favoriteBtn.querySelector('i').classList.remove('bi-heart');
        favoriteBtn.querySelector('i').classList.add('bi-heart-fill');
        const textElement = favoriteBtn.querySelector('.favorite-text');
        if (textElement) textElement.textContent = 'お気に入り済み';
      } else {
        favoriteBtn.classList.remove('active');
        favoriteBtn.querySelector('i').classList.remove('bi-heart-fill');
        favoriteBtn.querySelector('i').classList.add('bi-heart');
        const textElement = favoriteBtn.querySelector('.favorite-text');
        if (textElement) textElement.textContent = 'お気に入り';
      }
    }
    
    function saveMovieData() {
      const movieTitle = document.querySelector('h2.seat-title')?.textContent.trim() || 
                        document.querySelector('h2')?.textContent.trim() || 
                        'タイトル不明';
      const movieImage = document.querySelector('.movie-image')?.src || 
                        document.querySelector('.img-fluid')?.src || 
                        '/static/images/noimage.jpg';
      
      const movieData = {
        id: movieId,
        title: movieTitle,
        image_url: movieImage
      };
      
      localStorage.setItem(`movie_${movieId}`, JSON.stringify(movieData));
      console.log('映画データを保存しました:', movieData);
    }
    
    function toggleFavorite() {
      const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
      const isFavorite = favorites.includes(movieId);
      
      if (isFavorite) {
        const newFavorites = favorites.filter(id => id !== movieId);
        localStorage.setItem('favorites', JSON.stringify(newFavorites));
      } else {
        favorites.push(movieId);
        localStorage.setItem('favorites', JSON.stringify(favorites));
        saveMovieData();
      }
      
      updateFavoriteButton();
      
      window.dispatchEvent(new CustomEvent('favoriteChanged', { 
        detail: { movieId, isFavorite: !isFavorite } 
      }));
    }
    
    // 初期状態を設定
    updateFavoriteButton();
    
    // クリックイベント
    favoriteBtn.addEventListener('click', toggleFavorite);
  }
  
  // 他のページからのお気に入り変更を監視
  window.addEventListener('favoriteChanged', function(e) {
    const favoriteBtn = document.getElementById('favoriteBtn');
    if (favoriteBtn && favoriteBtn.dataset.movieId === e.detail.movieId) {
      updateFavoriteButton();
    }
  });

  // ========================================
  // キャンセル機能
  // ========================================
  const cancelButtons = document.querySelectorAll(".open-cancel-modal");
  const cancelForm = document.getElementById("cancelForm");
  const cancelModalElement = document.getElementById("cancelModal");

  if (cancelButtons.length > 0 && cancelForm && cancelModalElement) {
    const cancelModal = new bootstrap.Modal(cancelModalElement);

    cancelButtons.forEach(button => {
      button.addEventListener("click", function () {
        const reservationId = this.getAttribute("data-reservation-id");
        // 正しいURLパターンに修正
        cancelForm.setAttribute("action", `/reservation/${reservationId}/cancel/`);
        cancelModal.show();
      });
    });
  }
});