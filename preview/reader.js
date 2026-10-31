/* 의존성 없는 정적 독서 화면. 브라우저의 CSS 단 조판으로 원문을 나눈다. */
"use strict";
const sections = JSON.parse(document.getElementById("book-content").textContent);
const flow = document.getElementById("book-flow");
const viewport = document.getElementById("reader");
const paper = document.getElementById("paper");
const previous = document.getElementById("previous");
const next = document.getElementById("next");
const sidebar = document.getElementById("sidebar");
const menuToggle = document.getElementById("menu-toggle");
const backdrop = document.getElementById("menu-backdrop");
const main = document.querySelector("main");
let sectionIndex = 0;
let columnIndex = 0;
let columns = 1;
let visibleColumns = 1;
let stride = 0;
let fontSize = 16;
let resizeTimer;
let loading = false;

const nav = document.getElementById("section-nav");
sections.forEach((section, i) => {
  const button = document.createElement("button");
  button.type = "button";
  button.innerHTML = `<span aria-hidden="true">${String(i + 1).padStart(2, "0")}</span>${section.title}`;
  button.addEventListener("click", () => { showSection(i); toggleMenu(false); });
  nav.append(button);
});

function toggleMenu(open) {
  sidebar.classList.toggle("is-open", open);
  backdrop.hidden = !open;
  menuToggle.setAttribute("aria-expanded", String(open));
  menuToggle.setAttribute("aria-label", open ? "미리보기 목차 닫기" : "미리보기 목차 열기");
  sidebar.inert = innerWidth <= 900 && !open;
  main.inert = innerWidth <= 900 && open;
  if (open) nav.querySelector('[aria-current="page"]')?.focus();
  else if (sidebar.contains(document.activeElement) && innerWidth <= 900) menuToggle.focus();
}
menuToggle.addEventListener("click", () => toggleMenu(!sidebar.classList.contains("is-open")));
backdrop.addEventListener("click", () => { toggleMenu(false); menuToggle.focus(); });

function updateControls() {
  const section = sections[sectionIndex];
  previous.disabled = sectionIndex === 0 && columnIndex === 0;
  next.disabled = sectionIndex === sections.length - 1 && columnIndex + visibleColumns >= columns;
  document.getElementById("section-label").textContent = section.title;
  const end = Math.min(columnIndex + visibleColumns, columns);
  const pages = end > columnIndex + 1 ? `${columnIndex + 1}–${end}` : String(columnIndex + 1);
  document.getElementById("page-label").textContent = `${section.title} · ${pages} / ${columns}`;
  document.getElementById("reader-help").textContent = window.matchMedia("(pointer:coarse)").matches
    ? "화면을 좌우로 밀거나 버튼으로 넘겨보세요." : "좌우 방향키로 페이지를 넘겨보세요.";
  const progress = ((sectionIndex + end / columns) / sections.length) * 100;
  document.getElementById("progress-fill").style.width = `${progress}%`;
  document.getElementById("progress").setAttribute("aria-valuenow", String(Math.round(progress)));
  document.getElementById("font-label").textContent = String(fontSize);
  document.getElementById("font-smaller").disabled = fontSize <= 16;
  document.getElementById("font-larger").disabled = fontSize >= 24;
  [...nav.children].forEach((button, i) => {
    if (i === sectionIndex) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  flow.style.transform = `translateX(${-columnIndex * stride}px)`;
  // transformed content가 focus 때 가로 스크롤되면 조판 위치와 불일치하므로 고정한다.
  viewport.scrollLeft = 0;
}

function measure(preserveRatio = true) {
  const ratio = preserveRatio && columns > 1 ? columnIndex / columns : 0;
  flow.style.transform = "none";
  const width = viewport.clientWidth;
  const height = viewport.clientHeight;
  visibleColumns = width >= 770 && sections[sectionIndex].id !== "title" ? 2 : 1;
  const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--column-gap"));
  const columnWidth = (width - (visibleColumns - 1) * gap) / visibleColumns;
  document.documentElement.style.setProperty("--column-width", `${columnWidth}px`);
  document.documentElement.style.setProperty("--flow-height", `${height}px`);
  paper.classList.toggle("spread", visibleColumns === 2);
  stride = columnWidth + gap;
  columns = Math.max(1, Math.round((flow.scrollWidth + gap) / stride));
  columnIndex = Math.min(Math.floor((ratio * columns) / visibleColumns) * visibleColumns,
    Math.floor((columns - 1) / visibleColumns) * visibleColumns);
  updateControls();
  viewport.setAttribute("aria-busy", "false");
}

async function showSection(index, last = false, setHash = true) {
  if (index < 0 || index >= sections.length) return;
  loading = true;
  sectionIndex = index;
  columnIndex = 0;
  columns = 1;
  const section = sections[index];
  viewport.setAttribute("aria-busy", "true");
  flow.classList.toggle("is-contents", section.id === "contents");
  flow.innerHTML = section.blocks.join("\n");
  flow.querySelectorAll(".table-window").forEach(table => {
    table.tabIndex = 0;
    table.setAttribute("role", "region");
    table.setAttribute("aria-label", "표: 안에서 좌우·위아래로 스크롤할 수 있습니다");
  });
  flow.querySelectorAll(".manual-figure").forEach(figure => {
    const image = figure.querySelector("img");
    if (!image) return;
    const enlarge = document.createElement("a");
    enlarge.href = image.getAttribute("src");
    enlarge.target = "_blank";
    enlarge.rel = "noopener";
    enlarge.className = "image-enlarge";
    enlarge.textContent = "그림 크게 보기 ↗";
    enlarge.setAttribute("aria-label", `${image.alt} — 원본 이미지 크게 보기`);
    figure.append(enlarge);
    image.addEventListener("click", () => enlarge.click());
  });
  flow.querySelector("[data-start]")?.addEventListener("click", () => showSection(1));
  const pending = [...flow.querySelectorAll("img")].map(image => image.decode().catch(() => {}));
  await Promise.all([document.fonts.ready, ...pending]);
  if (sectionIndex !== index) return;
  measure(false);
  if (last) {
    columnIndex = Math.floor((columns - 1) / visibleColumns) * visibleColumns;
    updateControls();
  }
  if (setHash) history.replaceState(null, "", `#${section.id}`);
  document.title = `${section.title} · 감을 확신으로 바꾸는 AI 부동산 투자`;
  loading = false;
}

function turn(direction) {
  if (loading) return;
  if (direction > 0) {
    if (columnIndex + visibleColumns < columns) columnIndex += visibleColumns;
    else if (sectionIndex < sections.length - 1) { showSection(sectionIndex + 1); return; }
  } else {
    if (columnIndex > 0) columnIndex = Math.max(0, columnIndex - visibleColumns);
    else if (sectionIndex > 0) { showSection(sectionIndex - 1, true); return; }
  }
  updateControls();
}
previous.addEventListener("click", () => turn(-1));
next.addEventListener("click", () => turn(1));
document.addEventListener("keydown", event => {
  if (event.key === "Tab" && sidebar.classList.contains("is-open")) {
    const links = [...sidebar.querySelectorAll("a,button")];
    if (event.shiftKey && document.activeElement === links[0]) {
      event.preventDefault(); links.at(-1).focus();
    } else if (!event.shiftKey && document.activeElement === links.at(-1)) {
      event.preventDefault(); links[0].focus();
    }
  }
  if (event.key === "Escape" && sidebar.classList.contains("is-open")) {
    toggleMenu(false); menuToggle.focus(); return;
  }
  if (event.altKey || event.metaKey || event.ctrlKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)
      || event.target.isContentEditable || event.target.closest(".table-window")
      || sidebar.classList.contains("is-open")) return;
  if (event.key === "ArrowRight") { event.preventDefault(); turn(1); }
  if (event.key === "ArrowLeft") { event.preventDefault(); turn(-1); }
});
function changeFont(delta) {
  fontSize = Math.max(16, Math.min(24, fontSize + delta));
  document.documentElement.style.setProperty("--font-size", `${fontSize}px`);
  measure();
}
document.getElementById("font-smaller").addEventListener("click", () => changeFont(-2));
document.getElementById("font-larger").addEventListener("click", () => changeFont(2));
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { measure(); toggleMenu(false); }, 140);
});
window.addEventListener("hashchange", () => {
  const index = sections.findIndex(section => section.id === location.hash.slice(1));
  if (index >= 0 && index !== sectionIndex) showSection(index, false, false);
});
let startTouch = null;
viewport.addEventListener("touchstart", event => {
  startTouch = null;
  if (event.touches.length !== 1 || event.target.closest("a,button,.table-window")) return;
  startTouch = {x:event.touches[0].clientX,y:event.touches[0].clientY};
}, {passive:true});
viewport.addEventListener("touchend", event => {
  if (!startTouch || !event.changedTouches.length) return;
  const dx = event.changedTouches[0].clientX - startTouch.x;
  const dy = event.changedTouches[0].clientY - startTouch.y;
  startTouch = null;
  if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5 && !window.getSelection().toString()) turn(dx < 0 ? 1 : -1);
}, {passive:true});
viewport.addEventListener("touchcancel", () => { startTouch = null; }, {passive:true});
// 키보드로 본문 링크에 도달하면 해당 링크가 있는 펼침면도 함께 보여준다.
flow.addEventListener("focusin", event => {
  const offset = event.target.getBoundingClientRect().left - flow.getBoundingClientRect().left;
  const focusedColumn = Math.max(0, Math.round(offset / stride));
  columnIndex = Math.min(Math.floor(focusedColumn / visibleColumns) * visibleColumns,
    Math.floor((columns - 1) / visibleColumns) * visibleColumns);
  updateControls();
});
toggleMenu(false);
const initial = sections.findIndex(section => section.id === location.hash.slice(1));
showSection(initial >= 0 ? initial : 0);
