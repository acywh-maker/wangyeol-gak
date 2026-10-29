// 완결각 — 작은 화면 보조 스크립트. 스크립트가 없어도 모든 폼은 그대로 동작한다.
(function () {
  const post = (url, data) =>
    fetch(url, { method: "POST", body: data, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });

  // S4 예측 선택: 페이지 새로고침 없이 저장하고 선택 표시만 바꾼다 (정답은 보여 주지 않음)
  document.querySelectorAll("form[data-fetch]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const btn = e.submitter;
      if (!btn) return;
      e.preventDefault();
      const data = new FormData(form);
      data.set(btn.name, btn.value);
      post(form.action, data).then((r) => {
        if (!r.ok) return form.submit();
        form.querySelectorAll("button[name=choice]").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      });
    });
  });

  // S4 오늘의 한 줄: 입력을 마치면(포커스가 빠지면) 저장
  document.querySelectorAll("textarea[data-autosave]").forEach((ta) => {
    let last = ta.value;
    ta.addEventListener("change", () => {
      if (ta.value === last) return;
      const data = new FormData();
      data.set("line", ta.value);
      post(ta.dataset.autosave, data).then(() => (last = ta.value));
    });
  });

  // S6 목표와 선물: 시간을 고르면 회차 수·선물 지점을 바로 다시 계산
  const goal = document.getElementById("goal");
  if (!goal) return;
  const previews = JSON.parse(goal.dataset.previews);
  const saved = JSON.parse(goal.dataset.letters || "{}");
  const typed = {}; // 지점별로 쓰던 편지 (시간을 바꿔도 지우지 않음)
  const hidden = goal.querySelector("input[name=minutes]");
  const custom = goal.querySelector("input[name=custom_minutes]");
  const midBox = goal.querySelector("[data-mid-letters]");
  const finalLetter = goal.querySelector("textarea[name=letter_final]");

  function renderLetters(points) {
    midBox.querySelectorAll("textarea").forEach((t) => (typed[t.dataset.point] = t.value));
    midBox.innerHTML = "";
    points.slice(0, -1).forEach((p) => {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const label = document.createElement("label");
      label.className = "t-sub";
      label.textContent = `중간 선물 · ${p}화`;
      label.htmlFor = `letter_${p}`;
      const ta = document.createElement("textarea");
      ta.className = "textarea";
      ta.id = ta.name = `letter_${p}`;
      ta.maxLength = 500;
      ta.dataset.point = p;
      ta.placeholder = `${p}화까지 온 나에게 편지 쓰기…`;
      ta.value = typed[p] ?? saved[p] ?? "";
      wrap.append(label, ta);
      midBox.append(wrap);
    });
  }

  function show(total, points) {
    goal.querySelector("[data-total]").textContent = total;
    goal.querySelector("[data-last]").textContent = points[points.length - 1];
    const minutes = hidden.value;
    const marks = points.map((p, i) => `◆ ${p}화 ${i === points.length - 1 ? "완결" : "중간"} 선물`).join(" · ");
    goal.querySelector("[data-points]").textContent = `하루 ${minutes}분이면 ${total}화 · ${marks}`;
    renderLetters(points);
  }

  function update() {
    const choice = goal.querySelector("input[name=minutes_choice]:checked");
    const isCustom = choice && choice.value === "custom";
    custom.hidden = !isCustom;
    const minutes = Math.max(5, Math.min(180, parseInt(isCustom ? custom.value : choice.value, 10) || 10));
    hidden.value = minutes;
    if (previews[minutes]) return show(previews[minutes].total, previews[minutes].points);
    fetch(`${goal.dataset.previewUrl}?minutes=${minutes}`, { credentials: "same-origin" })
      .then((r) => r.json()).then((p) => { previews[minutes] = p; show(p.total, p.points); });
  }

  goal.querySelectorAll("input[name=minutes_choice]").forEach((r) => r.addEventListener("change", update));
  custom.addEventListener("change", update);
  goal.querySelectorAll("input[name=final_kind]").forEach((r) =>
    r.addEventListener("change", () => (finalLetter.hidden = r.value !== "letter_final" || !r.checked)));
  update();
})();
