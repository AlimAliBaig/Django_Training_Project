// Toggle between "equal" and "exact" split inputs on the expense form.
(function () {
  const select = document.getElementById("id_split_type");
  if (!select) return;
  const equalBox = document.getElementById("equalBox");
  const exactBox = document.getElementById("exactBox");
  const amount = document.getElementById("id_amount");
  const sumLabel = document.getElementById("exactSum");

  function refresh() {
    const exact = select.value === "exact";
    equalBox.classList.toggle("hidden", exact);
    exactBox.classList.toggle("hidden", !exact);
    updateSum();
  }
  function updateSum() {
    const inputs = exactBox.querySelectorAll("input[type=number]");
    let total = 0;
    inputs.forEach((i) => (total += parseFloat(i.value) || 0));
    const target = parseFloat(amount.value) || 0;
    sumLabel.textContent = "Entered: ₹" + total.toFixed(2) + " of ₹" + target.toFixed(2);
    sumLabel.style.color = Math.abs(total - target) < 0.005 ? "#4ade80" : "";
  }
  select.addEventListener("change", refresh);
  exactBox.addEventListener("input", updateSum);
  amount.addEventListener("input", updateSum);
  refresh();
})();
