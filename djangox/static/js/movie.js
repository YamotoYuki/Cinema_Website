document.addEventListener("DOMContentLoaded", function () {
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

  const selected = document.querySelector('input[name="date"]:checked');
  if (selected) updateTimeSlots(selected.dataset.weekday);

  dateRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      updateTimeSlots(radio.dataset.weekday);
    });
  });

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
