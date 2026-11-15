"use strict";
const status = document.getElementById("copy-status");
document.querySelectorAll("[data-copy]").forEach(button => {
  button.addEventListener("click", async () => {
    const filename = button.dataset.copy;
    button.disabled = true;
    button.textContent = "복사 중…";
    try {
      const response = await fetch(`files/${filename}`);
      if (!response.ok) throw new Error("자료를 불러오지 못했습니다.");
      const text = await response.text();
      if (!navigator.clipboard?.writeText) throw new Error("자동 복사를 지원하지 않는 브라우저입니다.");
      await navigator.clipboard.writeText(text);
      button.textContent = "복사 완료 ✓";
      status.textContent = "전문을 복사했습니다. 실습 프로젝트를 연 클로드 코드에 붙여 넣으세요.";
    } catch (_) {
      button.textContent = "다시 복사";
      status.textContent = "자동 복사가 되지 않았습니다. 해당 장의 ‘전문 열기’를 눌러 문안을 직접 복사해 주세요.";
    } finally {
      button.disabled = false;
    }
  });
});
