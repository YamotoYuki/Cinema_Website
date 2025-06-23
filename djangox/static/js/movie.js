document.addEventListener("DOMContentLoaded", function () {
  const dateRadios = document.querySelectorAll('input[name="date"]');
  const timeSlotContainer = document.getElementById('time-slot-container');

  const timeSlotMap = {
    "月": ["13:00～15:00", "16:00～18:00"],
    "火": ["13:00～15:00", "19:00～21:00"],
    "水": ["16:00～18:00", "19:00～21:00"],
    "木": ["13:00～15:00", "16:00～18:00", "19:00～21:00"],
    "金": ["13:00～15:00", "16:00～18:00", "19:00～21:00"],
    "土": ["13:00～15:00", "16:00～18:00", "19:00～21:00"],
    "日": ["13:00～15:00", "16:00～18:00", "19:00～21:00"]
  };

  function updateTimeSlots(weekday) {
    const slots = timeSlotMap[weekday] || [];
    timeSlotContainer.innerHTML = '';
    slots.forEach((slot, index) => {
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'time_slot';
      input.className = 'btn-check';
      input.id = 'time' + index;
      input.value = slot;
      if (index === 0) input.checked = true;

      const label = document.createElement('label');
      label.className = 'btn btn-outline-secondary';
      label.setAttribute('for', 'time' + index);
      label.textContent = slot;

      timeSlotContainer.appendChild(input);
      timeSlotContainer.appendChild(label);
    });
  }

  // 初期化
  const selected = document.querySelector('input[name="date"]:checked');
  if (selected) updateTimeSlots(selected.dataset.weekday);

  // 日付選択変更時
  dateRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      updateTimeSlots(radio.dataset.weekday);
    });
  });

  // キャンセルモーダル制御
  const cancelButtons = document.querySelectorAll(".open-cancel-modal");
  const cancelForm = document.getElementById("cancelForm");
  const cancelModal = new bootstrap.Modal(document.getElementById("cancelModal"));

  cancelButtons.forEach(button => {
    button.addEventListener("click", function () {
      const reservationId = this.getAttribute("data-reservation-id");
      cancelForm.setAttribute("action", `/reservation/${reservationId}/cancel/`);
      cancelModal.show();
    });
  });
});
